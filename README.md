# CanOpenPyFEWS

Python scripts to support data access for hydrological forecasting.

This repository can be used to access a number of operational data sources used for hydrological forecasting.
Threading is used to allow fast data access of multiple files, and the scripts are structured to allow easy maintenance via a settings file and addition of new products.

Current data sources include:
- [Meteorological Service of Canada Open Data](https://eccc-msc.github.io/open-data/readme_en/)
  - Numerical Weather Prediction (HRDPS, RDPS, GDPS, GEPS, REPS)
  - Recent Reanalysis Precipitation (HRDPA, RDPA)
  - Radar (Experimental Product - Password Protected)
- Snow Monitoring data
  - [Snowcast](http://www.snowcast.ca/)
  - [SNODAS](https://nsidc.org/data/g02158/versions/1)
  - [GlobSnow](https://www.globsnow.info/)
- Reanalysis products
  - ERA5 Reanalysis ([Copernicus Registration Required]((https://cds.climate.copernicus.eu/api-how-to)))

Note that these scripts are compatible and integrated into the [CanOpenFEWS](https://github.com/Deltares/CanOpenFEWS) forecasting system built with the Delft-FEWS framework.

## Usage

1. Follow installation instructions, such as installing required packages (see [Installation](#installation))
2. Run the script from the command line by navigating to the directory containing the script and executing:
    ```
    python can_open_py_fews.py --data-source SNODAS
    ```
Available options for data sources include:
- ECCC_NWP (also specify --model HRDPS/RDPS/GDPS/REPS/GEPS)
- ECCC_PRECIP_GRID (also specify --model HRDPA/RDPA)
- ECCC Radar
- ERA5
- SNODAS
- SNOWCAST
- GLOBSNOW

3. Alternatively, the can_open_py_fews.py can be run from an IDE, see settings under the if `__name__ == '__main__'` section.

Available data products, and their specific settings are held in the [download settings file](./settings/data_download_settings.yaml).

### Additional Command Line Arguments
- `--model`: Specify the model when using ECCC NWP as the data source. For example:
    ```
    python can_open_py_fews.py --data-source ECCC_NWP --model MODEL_NAME
    ```

- `--run_info_file`: Path to the run info file, when provided from Delft-FEWS required for data download. For example:
    ```
    python can_open_py_fews.py --run_info_file path/to/run_info_file.xml
    ```

- `--use-default-settings`: Use the default settings from the provided YAML configuration file. For example:
    ```
    python can_open_py_fews.py --use-default-settings True
    ```

## Installation
To install this project, follow these steps:

1. Clone the repository:
    ```
    git clone https://github.com/DaveCasson/CanOpenPyFEWS
    ```
2. Navigate to the project directory:
    ```
    cd CanOpenPyFEWS
    ```

3. Create a virtual environment (optional but recommended):
    ```
    python -m venv canopenpyfews
    ```
    Activate the virtual environment:
    - On Windows:
        ```
        .\canopenpyfews\Scripts\activate
        ```
    - On Unix or MacOS:
        ```
        source canopenpyfews/bin/activate
        ```

4. Install the required packages:
    ```
    pip install -r requirements.txt
    ```

## Contributing
We welcome contributions from the community! Here are the steps to contribute:

1. **Fork the Repository**: Click the 'Fork' button at the top right of this page. This will create a copy of this repository in your account.

2. **Clone Your Fork**: Clone the forked repository to your local machine. Replace `your-username` with your GitHub username.
    ```
    git clone https://github.com/your-username/CanOpenPyFEWS
    ```

3. **Create a Branch**: Create a new branch for your modifications. Use a descriptive branch name.
    ```
    git checkout -b your-branch-name
    ```

4. **Make Your Changes**: Make the necessary modifications to the codebase. Please keep the changes focused and understandable.

5. **Commit and Push**: After making your changes, commit and push them to your branch.
    ```
    git add .
    git commit -m "Add your commit message here"
    git push origin your-branch-name
    ```

6. **Create a Pull Request**: Go to your fork on GitHub and click the 'Compare & pull request' button. Fill in an informative description of your changes and submit the pull request.

7. **Code Review**: Wait for the project maintainers to review your pull request. Be open to feedback and make changes if requested.

### Reporting Issues
If you find any bugs or issues, please report them by creating an issue on GitHub. Provide as much information as possible to help us understand and fix the problem.

## License
This project is licensed under the MIT License.
