"""
ECMWF IFS / AIFS downloads (ENS and deterministic)

Uses ECMWF open-data (ecmwf-opendata) to download forecasts (IFS or AIFS)
and convert GRIB2 -> NetCDF with xarray + cfgrib, including an ensemble
dimension:

    int ens(ens=...);
      ens:_CoordinateAxisType = "Ensemble";

Also supports optional spatial clipping to a user-provided bounding box
(read from YAML settings):

    clip_to_bbox: true/false
    clip_bbox:
      lon_min: ...
      lon_max: ...
      lat_min: ...
      lat_max: ...

Model behaviour is controlled via YAML. For each model configuration
(e.g. ECMWF_NWP / IFS_ENS or ECMWF_NWP / AIFS_ENS) you can define:

    ecmwf_model: ifs / aifs-ens / aifs-single      # passed to Client(model=…)
    stream: enfo / oper / ...                      # passed as "stream"
    use_control: true/false                        # download separate control?
    control_type: cf / fc / ...                    # type for control forecast
    control_number: null or int                    # optional 'number' for control

    ensemble_type: pf / fc / ...                   # type for ensemble members
    ensemble_members: 0 or N                       # N > 0 => use 1..N if no explicit list
    ensemble_numbers: [] or [1,2,...]              # optional explicit list

If the *model name* (the key you pass into build_threads) contains
'DET' or 'SINGLE' (case-insensitive), this script will treat that
configuration as deterministic and will not request any ensemble members,
even if ensemble settings are provided in the YAML.

IFS original access develop Shahram Sahraei, Hydrologic Forecast Engineer,
Hydrologic Forecast Centre, Manitoba Transportation and Infrastructure,
November 2022.

Adapted and integrated by Dave Casson, Feb 2025
Updated to generic IFS/AIFS ENS via ecmwf-opendata + cfgrib, Dec 2025
"""

import os
import logging
import datetime as dt
import threading
import re
import netCDF4 as nc
import xarray as xr

# ECMWF open-data client
from ecmwf.opendata import Client

# Import local packages
from download_utils import start_thread, get_reference_time
from logging_utils import log2xml
from download_settings import read_download_settings

# Initialize the logger with the same settings
ds_dict = read_download_settings()
logger = logging.getLogger(ds_dict["logger_name"])

def _ecmwf_retrieve_thread(client, desc, retrieve_args, outputFile,
                           threadLimiter, maximumNumberOfThreads):
    """
    Thread worker for ECMWF open-data retrieval, mirroring the pattern used
    in data_download(): bounded semaphore, skip if file exists, detailed logging.
    """
    semaphore_acquired = False

    try:
        # Check if file already exists
        if os.path.isfile(outputFile):
            logger.info("File %s already exists. Download cancelled (%s).", outputFile, desc)
            return False

        # Acquire the semaphore
        threadLimiter.acquire()
        semaphore_acquired = True

        logger.info("Starting ECMWF job: %s -> %s", desc, outputFile)
        client.retrieve(**retrieve_args)
        logger.info("Finished ECMWF job: %s -> %s", desc, outputFile)
        return True

    except Exception as e:
        logger.warning("Unexpected error for ECMWF job '%s': %s", desc, e, exc_info=True)
        return False

    finally:
        if semaphore_acquired:
            threadLimiter.release()
            semaphore_acquired = False

        # Log thread information (like your original code)
        max_allowed = maximumNumberOfThreads
        activeThreads = threading.active_count() - 1
        logger.debug(
            "Maximum Number of Concurrent Threads Allowed = %s, "
            "Number of Threads Active = %s",
            max_allowed,
            activeThreads,
        )

        if ds_dict.get("xml_Log"):
            log2xml(ds_dict["log_file"], ds_dict["log_xml_file"])

def build_time_strs(timestep, interval, delay_hours, max_lead_time, first_lead_time):
    """
    Original helper to build date/time strings and lead times.

    NOTE: For ECMWF open-data we now use the actual latest run from the server
    (via Client.latest), so this function is kept for compatibility but no
    longer determines the run date/hour. It is still used to build the list
    of lead times from the YAML config if needed.
    """
    # reference time is utc+00 - configurable delay (cfs data is in utc+00)
    refDate = get_reference_time(delay_hours * 3600)

    # time stamps
    day_str = refDate.date().strftime("%Y%m%d")
    hour_str = "%02d" % (interval * int(refDate.time().hour / interval))

    # list with lead times to download
    lead_times = []
    for lt in range(first_lead_time, max_lead_time + timestep, timestep):
        lead_times.append(str(lt))

    return day_str, hour_str, lead_times

def build_threads(cmd_dict, data_source="ECMWF_NWP", model="IFS_ENS"):
    """
    Build downloads using ECMWF open-data for IFS or AIFS (ensemble or deterministic).

    Uses threading + a BoundedSemaphore, similar to the legacy HTTP downloader:
    - One thread per ECMWF retrieve() job
    - Concurrency limited by max_num_threads
    - Returns (download_threads, filenames), where download_threads is a list
      of Thread objects that the caller may join() before conversion.
    """
    global ds_dict
    ds_dict = cmd_dict

    max_num_threads = cmd_dict["max_num_threads"]
    output_dir = cmd_dict["output_dir"]

    # Model-specific parameters from YAML
    cfg = cmd_dict[data_source][model]

    delay_hours = cfg["delay"]
    lead_time = cfg["lead_time"]
    interval = cfg["interval"]
    timestep = cfg["timestep"]
    first_lead_time = cfg["first_lead_time"]
    parameters = cfg["parameters"]

    source = cfg.get("source", "aws")  # 'aws', 'ecmwf', 'google', 'azure'
    ecmwf_model = cfg.get("ecmwf_model", "ifs")  # 'ifs', 'aifs-ens', 'aifs-single', ...
    stream = cfg.get("stream", "enfo")          # 'enfo' for ENS, 'oper' for HRES, etc.

    use_control = bool(cfg.get("use_control", True))
    control_type = cfg.get("control_type")      # e.g. 'cf', 'fc'
    control_number = cfg.get("control_number", None)

    ensemble_type = cfg.get("ensemble_type", None)  # e.g. 'pf', 'fc'
    ensemble_members = int(cfg.get("ensemble_members", 0))
    ensemble_numbers_cfg = cfg.get("ensemble_numbers", None)

    # Determine whether this configuration is deterministic by model-name convention.
    model_upper = str(model).upper()
    is_deterministic_variant = ("DET" in model_upper) or ("SINGLE" in model_upper)

    threadLimiter = threading.BoundedSemaphore(max_num_threads)
    logger.info(
        "ECMWF open-data: threading enabled for downloads "
        "(max_num_threads=%d, legacy style).",
        max_num_threads,
    )

    # Enforce deterministic behaviour for DET/SINGLE variants.
    if is_deterministic_variant:
        if ensemble_type or ensemble_members > 0 or ensemble_numbers_cfg:
            logger.info(
                "Model '%s' detected as DETERMINISTIC variant (DET/SINGLE). "
                "Ensemble configuration (type=%s, members=%d) will be ignored.",
                model,
                ensemble_type,
                ensemble_members,
            )
        ensemble_type = None
        ensemble_members = 0
        ensemble_numbers_cfg = None

        logger.info(
            "Configuration '%s' treated as DETERMINISTIC: ecmwf_model='%s', "
            "stream='%s', control_type='%s', control_number=%s; no ensemble "
            "forecasts will be requested.",
            model,
            ecmwf_model,
            stream,
            control_type,
            control_number,
        )
    else:
        logger.info(
            "Configuration '%s' treated as ENSEMBLE/PROBABILISTIC: "
            "ecmwf_model='%s', stream='%s', use_control=%s, control_type='%s', "
            "ensemble_type='%s', ensemble_members=%d.",
            model,
            ecmwf_model,
            stream,
            use_control,
            control_type,
            ensemble_type,
            ensemble_members,
        )

    download_threads = []
    filenames = []

    # ---------------------------------------------------------------------
    # 1. Create ECMWF open-data client for chosen model (IFS / AIFS)
    # ---------------------------------------------------------------------
    logger.info(
        "Using ECMWF open-data with source='%s', model='%s', resol='0p25'.",
        source,
        ecmwf_model,
    )

    client = Client(
        source=source,
        model=ecmwf_model,
        resol="0p25",
    )

    # Determine which 'type' to use to query latest run
    latest_kwargs = {}
    if stream:
        latest_kwargs["stream"] = stream

    # Prefer control_type for latest(), else ensemble_type, else let client decide
    if use_control and control_type:
        latest_kwargs["type"] = control_type
    elif ensemble_type:
        latest_kwargs["type"] = ensemble_type

    latest_run = client.latest(**latest_kwargs) if latest_kwargs else client.latest()
    run_date = latest_run.date()
    run_hour = latest_run.hour

    logger.info(
        "Latest %s run (ECMWF open-data): %s (UTC)",
        ecmwf_model,
        latest_run,
    )

    # ---------------------------------------------------------------------
    # 2. Build lead times to download (from YAML config)
    # ---------------------------------------------------------------------
    lead_times = []
    for lt in range(first_lead_time, lead_time + timestep, timestep):
        lead_times.append(str(lt))

    logger.info(
        "Lead times to download (hours): %s",
        ", ".join(lead_times),
    )

    # Timestamp in filenames: YYYYMMDDHH0000-<lead>h-<stream>-<type>.grib2
    day_str = run_date.strftime("%Y%m%d")
    hour_str = f"{run_hour:02d}"

    # ---------------------------------------------------------------------
    # 3. Create threads for each control / ensemble job
    # ---------------------------------------------------------------------
    for lead_time_str in lead_times:
        step = int(lead_time_str)
        ref_time_str = f"{day_str}{hour_str}0000"
        base = f"{ref_time_str}-{lead_time_str}h-{stream}"

        # Control member job
        if use_control and control_type:
            cf_filename = f"{base}-{control_type}.grib2"
            cf_target = os.path.join(output_dir, cf_filename)

            retrieve_args = dict(
                date=run_date,
                time=run_hour,
                stream=stream,
                type=control_type,
                step=step,
                param=parameters,
                target=cf_target,
            )
            if control_number is not None:
                retrieve_args["number"] = control_number

            desc = f"control type={control_type} step={step}h for model={model}"
            thread = threading.Thread(
                target=_ecmwf_retrieve_thread,
                args=(
                    client,
                    desc,
                    retrieve_args,
                    cf_target,
                    threadLimiter,
                    max_num_threads,
                ),
            )
            thread.start()
            download_threads.append(thread)
            filenames.append(cf_filename)

        # Ensemble members job
        if ensemble_type and ensemble_members > 0:
            pf_filename = f"{base}-{ensemble_type}.grib2"
            pf_target = os.path.join(output_dir, pf_filename)

            if ensemble_numbers_cfg:
                ensemble_numbers = list(ensemble_numbers_cfg)
            else:
                ensemble_numbers = list(range(1, ensemble_members + 1))

            retrieve_args = dict(
                date=run_date,
                time=run_hour,
                stream=stream,
                type=ensemble_type,
                step=step,
                param=parameters,
                target=pf_target,
            )
            if ensemble_numbers:
                retrieve_args["number"] = ensemble_numbers

            desc = (
                f"ensemble type={ensemble_type} step={step}h "
                f"members={len(ensemble_numbers)} for model={model}"
            )
            thread = threading.Thread(
                target=_ecmwf_retrieve_thread,
                args=(
                    client,
                    desc,
                    retrieve_args,
                    pf_target,
                    threadLimiter,
                    max_num_threads,
                ),
            )
            thread.start()
            download_threads.append(thread)
            filenames.append(pf_filename)

    logger.info(
        "Started %d ECMWF download threads for model '%s'. "
        "Remember to join() these threads before conversion.",
        len(download_threads),
        model,
    )

    return download_threads, filenames


def parse_filename(filename):
    """
    Parses a filename like '20250224000000-9h-enfo-cf.grib2' or
    '20250224000000-9h-enfo-pf.grib2' to extract:
      - forecast_lead: forecast lead time as a 3-digit string (e.g., "009", "012", "138")

    It assumes the pattern:
      YYYYMMDDHHMMSS-<lead>h-<other_text>.grib2
    """
    basename = os.path.basename(filename)

    # Extract reference time from the first 14 characters
    ref_time_str = basename[:14]  # e.g., "20250224000000"

    # Extract forecast lead time by searching for a pattern like "-9h-"
    m = re.search(r"-(\d+)h-", basename)
    if m:
        forecast_lead_int = int(m.group(1))
    else:
        forecast_lead_int = 0  # default if pattern not found

    # Format the forecast lead time as a 3-digit string
    forecast_lead = f"{forecast_lead_int:03d}"

    return forecast_lead, ref_time_str


def _select_cfgrib_variables(ds, parameters):
    """
    Given an xarray Dataset `ds` from cfgrib and a list of GRIB shortNames
    (e.g. ['tp', '2t']), try to select matching variables.

    Matching rules (in order):
      1. NetCDF variable name equals the parameter (case-insensitive)
      2. Variable attribute GRIB_shortName or shortName equals the parameter
         (case-insensitive)

    Returns:
      ds_subset, selected_var_names
    """
    selected_var_names = []

    available_vars = list(ds.data_vars)
    logger.debug(
        "Available cfgrib variables: %s", ", ".join(available_vars)
    )

    for p in parameters:
        p_lc = p.lower()
        candidates = []

        # 1) Direct name match
        for name in ds.data_vars:
            if name.lower() == p_lc:
                candidates.append(name)

        # 2) Attribute-based match on GRIB_shortName / shortName
        for name, var in ds.data_vars.items():
            for attr_name in ("GRIB_shortName", "shortName"):
                sn = var.attrs.get(attr_name)
                if isinstance(sn, str) and sn.lower() == p_lc:
                    if name not in candidates:
                        candidates.append(name)

        if not candidates:
            logger.warning(
                "No variable found for GRIB param '%s'. Available vars: %s",
                p,
                ", ".join(available_vars),
            )
            continue

        # Take the first candidate as the canonical variable for this param
        chosen = candidates[0]
        if chosen not in selected_var_names:
            selected_var_names.append(chosen)
            logger.info(
                "GRIB param '%s' mapped to NetCDF variable '%s'.",
                p,
                chosen,
            )

    if not selected_var_names:
        return ds, []

    return ds[selected_var_names], selected_var_names


def _clip_dataset_to_bbox(ds, bbox):
    """
    Clip dataset `ds` to the bounding box defined by `bbox` dict:

        bbox = {
          'lon_min': ...,
          'lon_max': ...,
          'lat_min': ...,
          'lat_max': ...
        }

    - Detects longitude/latitude coordinate names ('longitude'/'latitude' or 'lon'/'lat')
    - Supports 1D lat/lon coords
    - Handles lon ranges 0..360 vs -180..180 by shifting requested bbox if needed
    - Uses a mask on coordinate centers; does not cut individual grid cells
    """
    lon_min = float(bbox["lon_min"])
    lon_max = float(bbox["lon_max"])
    lat_min = float(bbox["lat_min"])
    lat_max = float(bbox["lat_max"])

    # Detect coordinate names
    lon_name = None
    lat_name = None

    for cand in ("longitude", "lon"):
        if cand in ds.coords:
            lon_name = cand
            break
    if lon_name is None:
        for cand in ("longitude", "lon"):
            if cand in ds.dims:
                lon_name = cand
                break

    for cand in ("latitude", "lat"):
        if cand in ds.coords:
            lat_name = cand
            break
    if lat_name is None:
        for cand in ("latitude", "lat"):
            if cand in ds.dims:
                lat_name = cand
                break

    if lon_name is None or lat_name is None:
        logger.warning(
            "Could not find latitude/longitude coordinates for clipping. "
            "lon_name=%s, lat_name=%s",
            lon_name,
            lat_name,
        )
        return ds

    lon = ds[lon_name]
    lat = ds[lat_name]

    if lon.ndim != 1 or lat.ndim != 1:
        logger.warning(
            "Clipping is currently only implemented for 1D lon/lat grids. "
            "Got lon.ndim=%d, lat.ndim=%d",
            lon.ndim,
            lat.ndim,
        )
        return ds

    # Handle 0..360 vs -180..180
    lon_min_adj, lon_max_adj = lon_min, lon_max
    lon_max_val = float(lon.max().values)
    lon_min_val = float(lon.min().values)

    if lon_max_val > 180.1 and lon_min < 0:
        # Dataset longitudes likely 0..360, user provided -180..180
        lon_min_adj = lon_min + 360.0
        lon_max_adj = lon_max + 360.0
        logger.info(
            "Adjusting requested lon bbox from [%s,%s] to [%s,%s] for 0..360 grid.",
            lon_min,
            lon_max,
            lon_min_adj,
            lon_max_adj,
        )

    # Build masks
    lon_mask = (lon >= lon_min_adj) & (lon <= lon_max_adj)
    lat_low = min(lat_min, lat_max)
    lat_high = max(lat_min, lat_max)
    lat_mask = (lat >= lat_low) & (lat <= lat_high)

    # Apply masks via selecting the subset of coordinate values
    lon_sub = lon.where(lon_mask, drop=True)
    lat_sub = lat.where(lat_mask, drop=True)

    if lon_sub.size == 0 or lat_sub.size == 0:
        logger.warning(
            "Clipping bbox resulted in empty domain. "
            "Requested lon=[%s,%s], lat=[%s,%s]. "
            "Available lon=[%s,%s], lat=[%s,%s].",
            lon_min,
            lon_max,
            lat_min,
            lat_max,
            float(lon_min_val),
            float(lon_max_val),
            float(lat.min().values),
            float(lat.max().values),
        )
        return ds

    ds_clipped = ds.sel({lon_name: lon_sub, lat_name: lat_sub})

    # Use .sizes instead of .dims to avoid xarray FutureWarning
    lon_size = ds_clipped.sizes.get(lon_name, None)
    lat_size = ds_clipped.sizes.get(lat_name, None)

    logger.info(
        "Clipped dataset to lon=[%s,%s], lat=[%s,%s] "
        "(grid cells: %s x %s).",
        float(ds_clipped[lon_name].min().values),
        float(ds_clipped[lon_name].max().values),
        float(ds_clipped[lat_name].min().values),
        float(ds_clipped[lat_name].max().values),
        lon_size,
        lat_size,
    )

    return ds_clipped
def convert_grib_to_netcdf(
    cmd_dict, filenames, data_source="ECMWF_NWP", model="IFS_ENS"
):
    """
    Converts each GRIB2 file in 'filenames' to a NetCDF file using xarray + cfgrib.

    - Uses the same output directory as the downloader:
        model_cfg.get("output_dir", cmd_dict["output_dir"])
    - Reads the GRIB2 with cfgrib
    - Selects only the variables listed in cmd_dict[data_source][model]['parameters']
      (e.g., ['tp', '2t']) by matching GRIB_shortName / shortName
    - Renames ensemble dimension from 'number' to 'ens' and tags:
         ens:_CoordinateAxisType = "Ensemble"
    - Adds a 'forecast_reference_time' coordinate based on the filename
    - **NEW**: Promotes scalar valid_time/time to a proper 'time' dimension,
      so FEWS can parse a time axis on the data variables.
    - Optionally clips to a user-specified bounding box if:
         clip_to_bbox: true
         clip_bbox: {lon_min, lon_max, lat_min, lat_max}
    - Writes NetCDF into the SAME output directory as the GRIB2
    - Deletes the original GRIB2 file

    Filename pattern expected:
      YYYYMMDDHHMMSS-<lead>h-<other_text>.grib2
    """

    # Allow per-model override of output_dir, but fall back to global.
    model_cfg = cmd_dict[data_source][model]
    parameters = model_cfg["parameters"]

    output_dir = model_cfg.get("output_dir", cmd_dict["output_dir"])
    clip_to_bbox = bool(model_cfg.get("clip_to_bbox", False))
    clip_bbox = model_cfg.get("clip_bbox", None)

    # Make sure the target directory exists
    os.makedirs(output_dir, exist_ok=True)

    logger.info(
        "Converting %d GRIB2 files to NetCDF for '%s'. "
        "Output directory for NetCDF: %s",
        len(filenames),
        model,
        os.path.abspath(output_dir),
    )

    for filename in filenames:
        # GRIB2 and NetCDF paths both under the SAME output_dir
        grib2_path = os.path.join(output_dir, filename)

        # Parse the filename to get forecast lead time and reference time string
        forecast_lead, ref_time_str = parse_filename(filename)
        netcdf_filename = f"{ref_time_str}_{forecast_lead}H.nc"
        netcdf_path = os.path.join(output_dir, netcdf_filename)

        logger.debug(
            "Preparing conversion for %s -> %s",
            grib2_path,
            netcdf_path,
        )

        # Read GRIB2 with cfgrib
        try:
            ds = xr.open_dataset(
                grib2_path,
                engine="cfgrib",
                backend_kwargs={"indexpath": ""},  # no sidecar index files
            )
        except Exception as e:
            logger.error("Error opening GRIB2 %s with cfgrib: %s", grib2_path, e)
            continue

        # Subset variables based on parameters list (GRIB shortNames)
        ds_sel, selected_vars = _select_cfgrib_variables(ds, parameters)
        if not selected_vars:
            logger.warning(
                "No variables matching %s found in %s; writing full dataset.",
                parameters,
                filename,
            )
            ds_sel = ds

        # Rename ensemble dimension 'number' -> 'ens' and tag axis
        if "number" in ds_sel.dims:
            ds_sel = ds_sel.rename({"number": "ens"})
            if "ens" in ds_sel.coords:
                ds_sel["ens"].attrs["_CoordinateAxisType"] = "Ensemble"
        else:
            # For deterministic variants, this is expected.
            logger.info(
                "No 'number' dimension in dataset for %s; treating as deterministic.",
                filename,
            )

        # Add forecast_reference_time coordinate from filename (YYYYMMDDHHMMSS)
        try:
            frt = dt.datetime.strptime(ref_time_str, "%Y%m%d%H%M%S")
            ds_sel = ds_sel.assign_coords(forecast_reference_time=frt)
            ds_sel["forecast_reference_time"].attrs.update(
                {
                    "standard_name": "forecast_reference_time",
                    "long_name": "Forecast reference time",
                    "comments": "Derived from GRIB file name.",
                }
            )
        except Exception as e:
            logger.warning(
                "Could not parse forecast_reference_time from %s: %s",
                ref_time_str,
                e,
            )

        # ------------------------------------------------------------------
        # NEW: Promote scalar valid_time/time to a real 'time' dimension
        # ------------------------------------------------------------------
        try:
            time_val = None

            # Prefer valid_time if present (actual forecast valid time)
            if "valid_time" in ds_sel.variables:
                vt_var = ds_sel["valid_time"]
                time_val = vt_var.values
            elif "time" in ds_sel.variables:
                t_var = ds_sel["time"]
                time_val = t_var.values

            if time_val is not None:
                # If there is a scalar 'time' variable, drop it before promoting
                if "time" in ds_sel.variables and "time" not in ds_sel.dims:
                    ds_sel = ds_sel.drop_vars("time")

                if "time" not in ds_sel.dims:
                    # Create a time dimension of length 1 and broadcast vars
                    ds_sel = ds_sel.expand_dims(time=[time_val])

                    # Overwrite/create time coord explicitly (1D)
                    ds_sel["time"] = ("time", [time_val])
                    ds_sel["time"].attrs.update(
                        {
                            "standard_name": "time",
                            "long_name": "valid time of forecast",
                            # units will be handled by xarray CF encoding
                        }
                    )

                # Optionally, tie valid_time to the time axis as well
                if "valid_time" in ds_sel.variables and "time" in ds_sel.dims:
                    # Make valid_time a 1D coord aligned with time
                    vt = ds_sel["valid_time"]
                    ds_sel = ds_sel.drop_vars("valid_time")
                    ds_sel = ds_sel.assign_coords(
                        valid_time=("time", [time_val])
                    )
                    ds_sel["valid_time"].attrs.update(vt.attrs)

        except Exception as e:
            logger.warning(
                "Could not promote scalar time/valid_time to 'time' dimension for %s: %s",
                filename,
                e,
            )

        # ------------------------------------------------------------------
        # NEW: Put dimensions in a consistent order: time, ens, lat, lon
        # ------------------------------------------------------------------
        try:
            preferred = []
            for dim in ("time", "ens", "latitude", "lat", "longitude", "lon"):
                if dim in ds_sel.dims and dim not in preferred:
                    preferred.append(dim)
            # Add any remaining dims at the end
            for dim in ds_sel.dims:
                if dim not in preferred:
                    preferred.append(dim)

            if preferred and list(ds_sel.dims) != preferred:
                ds_sel = ds_sel.transpose(*preferred)
        except Exception as e:
            logger.warning(
                "Could not reorder dimensions for %s; keeping original order. Error: %s",
                filename,
                e,
            )

        # Optional clipping to bounding box
        if clip_to_bbox and clip_bbox is not None:
            try:
                ds_sel = _clip_dataset_to_bbox(ds_sel, clip_bbox)
            except Exception as e:
                logger.error("Error applying clipping to %s: %s", filename, e)

        # Write NetCDF
        try:
            logger.info("Writing NetCDF for %s to %s", filename, os.path.abspath(netcdf_path))
            ds_sel.to_netcdf(netcdf_path)
            print(f"Converted {grib2_path} to {netcdf_path}")
        except Exception as e:
            logger.error("Error writing NetCDF %s: %s", netcdf_path, e)
            continue
        finally:
            ds.close()
            ds_sel.close()

        # Delete the original GRIB2 file after a successful conversion
        try:
            os.remove(grib2_path)
            print(f"Deleted {grib2_path}")
        except OSError as e:
            print(f"Error deleting {grib2_path}: {e}")


