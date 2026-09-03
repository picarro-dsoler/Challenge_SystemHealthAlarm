"""
Generates and displays a report based on specified parameters.

To use this function, import the view_report function and
set the required variables 'customer' and 'report_id' to generate the report.
Optionally, you can also configure other parameters as described below.

Args:
    customer (str): Name of the customer. Example: 'Picarro'.
    report_id (str): Unique identifier for the report. Example: '341FA816'.
    downsample_factor (int, optional): Factor by which to downsample the number of breadcrumbs. Defaults to 1.
    plot_wind_arrows (bool, optional): If True, plots wind arrows; otherwise, plots point breadcrumbs. Defaults to True.
    custom_gps_points (list of dict, optional): A list of dictionaries to plot GPS points of interest.
        Each dictionary should contain 'latitude', 'longitude', 'Location', and 'Emission Rate'.
        This is also used as a reference to display nearby breadcrumbs.
        Example: [{'latitude': 37.42728033, 'longitude': -122.07712867, 'Location': 'A', 'Emission Rate': '0 scfh'}]
    breadcrumbs (bool, optional): Set to True to plot breadcrumbs. Requires a valid 'custom_gps_points' value. Defaults to False.

Returns:
    object: A map visualization object, typically of a specific library like Folium.

Example:
    To view a report with custom GPS points and breadcrumbs:
    >>> from gasanalytics.report_viewer import view_report
    >>> CUSTOMER = 'Picarro'
    >>> REPORT_ID = '341FA816'
    >>> custom_gps_points = [{'latitude': 37.42728033, 'longitude': -122.07712867, 'Location': 'A', 'Emission Rate': '0 scfh'}]
    >>> m = view_report(CUSTOMER, REPORT_ID, custom_gps_points=custom_gps_points, breadcrumbs=True)

    To save the report as an HTML file:
    >>> html_file_name = r'C:\\directory\\example.html'
    >>> m.save(html_file_name)
"""

import os
import sys
import numpy as np
import pandas as pd
import re
import geopandas as gpd
import folium
from matplotlib.colors import LinearSegmentedColormap, Normalize
import matplotlib.colors as mcolors
import uuid
import pytz
from datetime import datetime
from dotenv import load_dotenv
from psanalytics.utilities.coordinate_calculations import dist_vincenty
from apps_dal_sql.cursorfactory import CursorFactory
from apps_dal_dynamo.dynamodal import DynamoDalBase
import matplotlib.pyplot as plt
from folium.plugins import FloatImage
import base64
from io import BytesIO

pd.set_option("display.max_columns", 500)

load_dotenv(override=True)
LOG_SHIPPING_DB = "EU-SurveyorProduction2"
LOG_SHIPPING_PW = os.getenv("EU2DBPW")
LOG_SHIPPING_USER = os.getenv("EU2DBUSER")
LOG_SHIPPING_SERVER = "eu-prd2-sqlsrv-ee-db01.czz1yneu9gmr.eu-central-1.rds.amazonaws.com"
DYNAMO_DB_REGION = "eu-central-1"
DYNAMO_DB_ACCESS_KEY = os.getenv("DYNAMOACCESSKEYEU")
DYNAMO_DB_SECRET_KEY = os.getenv("DYNAMOSECRETKEYEU")
DYNAMO_DB_ENVIRONMENT = "EU-SurveyorProduction2"

assert LOG_SHIPPING_DB
assert DYNAMO_DB_ACCESS_KEY

cursor_factory = CursorFactory(
    server=LOG_SHIPPING_SERVER,
    user=LOG_SHIPPING_USER,
    password=LOG_SHIPPING_PW,
    database=LOG_SHIPPING_DB,
    tds_version="7.3",
)

dynamo_dal = DynamoDalBase(
    dynamo_db_region=DYNAMO_DB_REGION,
    dynamo_db_access_key=DYNAMO_DB_ACCESS_KEY,
    dynamo_db_secret_key=DYNAMO_DB_SECRET_KEY,
    dynamo_db_session_token=None,
    dynamo_db_environment=DYNAMO_DB_ENVIRONMENT,
    dynamo_db_local=False,
    dynamo_db_endpoint_url=None,
)


def view_report(
    customer,
    report_id,
    downsample_factor=1,
    plot_wind_arrows=True,
    custom_gps_points=False,
    breadcrumbs=False,
    output_path=False,
    emission_rate_threshold=2,
):
    """
    Generates and displays a report based on specified parameters.

    To use this function, set the required variables 'customer' and 'report_id' to generate the report.
    Optionally, you can also configure other parameters as described below.

    Args:
        customer (str): Name of the customer. Example: 'Picarro'.
        report_id (str): Unique identifier for the report. Example: '341FA816'.
        downsample_factor (int, optional): Factor by which to downsample the number of breadcrumbs. Defaults to 1.
        plot_wind_arrows (bool, optional): If True, plots wind arrows; otherwise, plots point breadcrumbs. Defaults to True.
        custom_gps_points (list of dict, optional): A list of dictionaries to plot GPS points of interest.
            Each dictionary should contain 'latitude', 'longitude', 'Location', and 'Emission Rate'.
            This is also used as a reference to display nearby breadcrumbs.
            Example: [{'latitude': 37.42728033, 'longitude': -122.07712867, 'Location': 'A', 'Emission Rate': '0 scfh'}]
        breadcrumbs (bool, optional): Set to True to plot breadcrumbs. Requires a valid 'custom_gps_points' value. Defaults to False.

    Returns:
        object: A map visualization object, typically of a specific library like Folium.

    Example:
        To view a report with custom GPS points and breadcrumbs:
        >>> custom_gps_points = [{'latitude': 37.42728033, 'longitude': -122.07712867, 'Location': 'A', 'Emission Rate': '0 scfh'}]
        >>> m = view_report('Picarro', '341FA816', custom_gps_points=custom_gps_points, breadcrumbs=True)

        To save the report as an HTML file:
        >>> html_file_name = r'C:\\Users\\Administrator\\Documents\\Picarro\\SE_Deep_Dives\\report_viewer\\Location_A_018scfh.html'
        >>> m.save(html_file_name)
    """

    report_es_df, peaks_df, fov3_df, breadcrumb_df = _process_dataframes(
        customer,
        report_id,
        cursor_factory,
        breadcrumbs,
        custom_gps_points,
        downsample_factor,
        emission_rate_threshold,
    )

    if breadcrumbs:
        window_size = downsample_factor
        breadcrumb_df = _calculate_rolling_average(breadcrumb_df, "CH4", window_size)
        downsampled_breadcrumb_df = _downsample_dataframe(
            breadcrumb_df, downsample_factor
        )
    else:
        downsampled_breadcrumb_df = None

    report_es_gdf, peaks_gdf, fov3_gdf, breadcrumb_gdf = _create_geodataframes(
        report_es_df, peaks_df, fov3_df, downsampled_breadcrumb_df
    )

    report_title = _get_report_title(report_id, customer, cursor_factory).ReportTitle[0]
    emission_rate = _extract_emission_rate(report_title)

    if custom_gps_points:
        custom_gps_points[0]["Emission Rate"] = emission_rate

    # Process dataframes
    _convert_datatypes(report_es_gdf)
    _convert_datatypes(fov3_gdf)
    _process_dataframe_columns(report_es_gdf)
    _process_dataframe_columns(peaks_gdf)

    def _convert_gdf_for_geopackage(gdf):
        """
        Converts a GeoDataFrame's columns to types compatible with GeoPackage.
        Specifically converts UUIDs to strings.
        """
        for col in gdf.columns:
            if col != gdf.geometry.name:
                # Convert UUIDs to string
                if isinstance(gdf[col].iloc[0], uuid.UUID):
                    gdf[col] = gdf[col].astype(str)
                # Add other type conversions if necessary
        return gdf

    if output_path:
        # Write each GeoDataFrame to the GeoPackage
        if report_es_gdf is not None:
            _convert_gdf_for_geopackage(report_es_gdf).to_file(
                output_path, layer="report_ES", driver="GPKG"
            )
        if peaks_gdf is not None:
            _convert_gdf_for_geopackage(peaks_gdf).to_file(
                output_path, layer="peaks", driver="GPKG"
            )
        if fov3_gdf is not None:
            _convert_gdf_for_geopackage(fov3_gdf).to_file(
                output_path, layer="FOV3", driver="GPKG"
            )
        if breadcrumb_gdf is not None:
            _convert_gdf_for_geopackage(breadcrumb_gdf).to_file(
                output_path, layer="breadcrumb", driver="GPKG"
            )

    # Initialize map
    m = _initialize_map(fov3_gdf)
    # Create a custom pane for wind direction arrows - this allows us to control wind arrow breadcrumb z-order
    folium.map.CustomPane(name="arrowPane", z_index=250).add_to(m)

    # Add FOV3 layer
    _add_geojson_to_map(
        fov3_gdf,
        m,
        style_function=lambda x: {"color": "blue"},
        include_tooltips=False,
        #         highlight_function=lambda x: {'weight': 2, 'color': 'cyan'}
    )

    min_ch4 = 2
    max_ch4 = 7
    if breadcrumbs:
        _process_dataframe_columns(breadcrumb_gdf)
        # Add breadcrumbs layer
        if plot_wind_arrows:
            _add_wind_direction_arrows(breadcrumb_gdf, m, min_ch4, max_ch4)
        else:
            # Add sorted breadcrumbs layer
            _add_markers(
                breadcrumb_gdf,
                m,
                "circle",
                min_ch4=min_ch4,
                max_ch4=max_ch4,
                color_field="CH4",
                radius=2
                #                     ,popup_fields=['DateTime', 'CH4', 'GpsLongitude', 'GpsLatitude']
            )

    # Add emission source layer
    _add_geojson_to_map(
        report_es_gdf,
        m,
        style_function=lambda x: {"color": "orange"},
        tooltip_fields=[
            "DateTime",
            "CH4",
            "Disposition",
            "EmissionRate",
            "IsFiltered",
            "PriorityScore",
            "GpsLatitude",
            "GpsLongitude",
        ],
        highlight_function=lambda x: {"weight": 3, "color": "red"},
    )

    # Add peaks layer
    _add_markers(
        peaks_gdf,
        m,
        "circle",
        color="cyan",
        popup_fields=[
            "DateTime",
            "CH4",
            "PeakEmissionRate",
            "Disposition",
            "Latitude",
            "Longitude",
        ],
        z_index_offset=200,
    )

    # Add custom GPS points layer
    if custom_gps_points:  # Check if custom GPS points are provided
        _add_custom_gps_points(
            m,
            custom_gps_points,
            marker_color="orange",
            popup_fields=["Location", "Emission Rate"],
        )

    # Add the colorbar to the map
    colorbar_url = _create_colorbar_with_labels_base64(2, 7)
    FloatImage(colorbar_url, bottom=2.5, left=15).add_to(m)

    # Generate and add the legend
    legend_html = _create_legend_html(
        fov_color="blue",
        peak_color="cyan",
        lisa_color = 'orange',
        breadcrumb_color="green",
    )
    m.get_root().html.add_child(folium.Element(legend_html))
    return m


def _get_lisa_coords(customer, report_id, lisa_number, creds):
    """
    Retrieves the coordinates of a specified LISA (Leak Indication by Spatial Analysis) number from a database.

    Args:
        customer (str): The name of the customer for which the report is being generated.
        report_id (str): The unique identifier for the report.
        lisa_number (int): The specific LISA number whose coordinates are being requested.
        creds (CursorFactory): A CursorFactory instance with database credentials.

    Returns:
        DataFrame: A pandas DataFrame containing the coordinates and additional information for the specified LISA.
    """
    query = """
SELECT
       R2.Id AS ReportId,
       C.Name,
       P.CH4,
       --P.Lisa,
       P.GpsLatitude as Latitude,
       P.GpsLongitude as Longitude,
       ES.Id AS SourceId,
       ES.PeakNumber,
       ES.CH4,
       -- ES.Lisa,
       ES.EmissionRate,
       ES.IsFiltered,
       ES.PriorityScore,
       ES.GpsLongitude as lisa_lon,
       ES.GpsLatitude as lisa_lat,
       ES.Disposition
FROM EmissionSource ES
LEFT JOIN Report R2 on ES.ReportId = R2.Id
LEFT JOIN Peak P ON ES.RepresentativePeakId = P.Id
LEFT JOIN Customer C ON R2.CustomerId = C.Id
WHERE C.Name = '{}' AND R2.Id LIKE '{}%' AND ES.EmissionRate >= 10;
                    """.format(
        customer, report_id
    )

    with creds.get_connection_pymssql() as conn:
        df = pd.read_sql(sql=query, con=conn)

    return df


def _get_surveys_in_report(customer, report_id, creds):
    """
    Retrieves survey data associated with a given report from the database.

    Args:
        customer (str): The name of the customer associated with the report.
        report_id (str): The unique identifier for the report.
        creds (CursorFactory): A CursorFactory instance with database credentials.

    Returns:
        DataFrame: A pandas DataFrame containing survey data for the specified report.
    """

    query = """
    SELECT
    CONVERT(NVARCHAR(50), R.Id)         AS ReportId,
    CONVERT(NVARCHAR(50), RDS.SurveyId) AS SurveyId,
    S.StartEpoch,
    S.EndEpoch,
    S.StartDateTime,
    S.EndDateTime,
    R.ReportTitle,
    C.Name,
    S.SurveyAreaBoundary.STAsText() as SHAPE,
    CONVERT(NVARCHAR(50), S.AnalyzerId) AS AnalyzerId
    FROM Report R
    FULL OUTER JOIN ReportDrivingSurvey RDS ON R.Id = RDS.ReportId
    JOIN Survey S ON RDS.SurveyId = S.Id
    LEFT JOIN Customer C ON R.CustomerId = C.Id
    WHERE C.Name = '{}' AND ReportId LIKE '{}%' AND SurveyAreaBoundary.STIsValid() = 1;
                    """.format(
        customer, report_id
    )

    with creds.get_connection_pymssql() as conn:
        df = pd.read_sql(sql=query, con=conn)

    return df


def _get_geom_type(st):
    """
    Extracts the geometry type from a spatial object represented as a string.

    Args:
        st (str): A string representation of a spatial object.

    Returns:
        tuple: A tuple containing the geometry type(s) found in the input string.
    """

    word1 = re.findall("[a-zA-Z]+", st)
    return tuple(word1)


def _get_timezone(report_id, customer, creds):
    """
    Determines the timezone for a given report and customer.

    Args:
        report_id (str): The unique identifier for the report.
        customer (str): The name of the customer associated with the report.
        creds (CursorFactory): A CursorFactory instance with database credentials.

    Returns:
        str: The timezone description associated with the report and customer.
    """

    query = f"""
    SELECT TimeZone.Description
    FROM TimeZone
    JOIN Report R on TimeZone.Id = R.TimeZoneId
    JOIN Customer C on R.CustomerId = C.Id
    WHERE C.Name = '{customer}' AND R.Id LIKE '{report_id}%';
    """
    with creds.get_connection_pymssql() as conn:
        df = pd.read_sql(sql=query, con=conn)
    return df["Description"][0]


"""
Function to add distance from origin to a set of measurements data
"""


def _add_distance(measurements_dataframe):
    """
    Adds a column to the dataframe indicating the cumulative distance traveled based on GPS coordinates.

    Args:
        measurements_dataframe (DataFrame): A pandas DataFrame containing GPS coordinates and fit quality.

    Returns:
        DataFrame: The original DataFrame augmented with a 'distance' column indicating cumulative distance.
    """

    measurements_dataframe["GpsLongitude"] = pd.to_numeric(
        measurements_dataframe["GpsLongitude"], errors="coerce"
    )
    measurements_dataframe["GpsLatitude"] = pd.to_numeric(
        measurements_dataframe["GpsLatitude"], errors="coerce"
    )

    dat = measurements_dataframe.to_dict("records")

    dist = None
    lastLat = None
    lastLng = None
    jumpMax = 500
    distance_values = []

    for newDat in dat:

        assert isinstance(newDat, dict)

        lng = newDat["GpsLongitude"]
        lat = newDat["GpsLatitude"]
        fit = newDat["GpsFit"]

        if fit < 1 or np.isnan(lng) or np.isnan(lat):
            result = np.nan
        else:
            if lastLat is None and lastLng is None:
                result = dist = 0.0
            else:
                jump = dist_vincenty(lat, lng, lastLat, lastLng)
                if jump < jumpMax:
                    dist += jump
                    result = dist
                else:
                    result = np.nan
            lastLat = lat
            lastLng = lng

        distance_values.append(result)

    measurements_dataframe["distance"] = distance_values
    return measurements_dataframe


def _get_emissions_source(customer, report_id, creds):
    """
    Retrieves information about emission sources from the database for a specified customer and report.

    Args:
        customer (str): The name of the customer.
        report_id (str): The unique identifier for the report.
        creds (CursorFactory): A CursorFactory instance with database credentials.

    Returns:
        DataFrame: A pandas DataFrame containing details about emission sources for the specified report.
    """

    query = """  
    SELECT
           R2.Id as report_id,
           R2.ReportTitle,
           C.Name,
           P.EpochTime,
           --P.CH4,
           --P.Lisa.STAsText() as PeakLisa,
           --P.GpsLatitude as peak_lat,
           --P.GpsLongitude as peak_lon,
           ES.Id AS EmissionSourceId,
           ES.CH4,
           ES.Lisa.STAsText() as EmissionSourceLisa,
           ES.EmissionRate,
           ES.IsFiltered,
           ES.PriorityScore,
           ES.GpsLongitude,
           ES.GpsLatitude,
           ES.Disposition
    FROM EmissionSource ES
    LEFT JOIN Report R2 on ES.ReportId = R2.Id
    LEFT JOIN Peak P ON ES.RepresentativePeakId = P.Id
    LEFT JOIN Customer C ON R2.CustomerId = C.Id

    WHERE (ES.Disposition = 1 OR ES.Disposition = 3) AND C.Name = '{}' AND R2.Id LIKE '{}%';
        ;
          """.format(
        customer, report_id
    )

    with cursor_factory.get_connection_pymssql() as conn:
        EmissionSource = pd.read_sql(sql=query, con=conn)
    return EmissionSource


def _get_peaks(creds, customer, report_id):
    """
    Retrieves peak emission data for a given customer and report ID.

    Args:
        creds (CursorFactory): A CursorFactory instance with database credentials.
        customer (str): The name of the customer.
        report_id (str): The unique identifier for the report.

    Returns:
        DataFrame: A pandas DataFrame containing peak emission data for the specified report.
    """

    query = """  
    SELECT
           R2.Id as report_id,
           C.Name,
           P.CH4,
           P.PlumeEmissionRate as PeakEmissionRate,
           P.EpochTime,
           --P.Lisa.STAsText() as PeakLisa,
           P.GpsLatitude as Latitude,
           P.GpsLongitude as Longitude,
           P.Disposition
    FROM Peak P
    LEFT JOIN Survey S ON P.SurveyId = S.Id
    LEFT JOIN ReportDrivingSurvey RDS ON RDS.SurveyId = S.Id
    LEFT JOIN Report R2 on RDS.ReportId = R2.Id
    LEFT JOIN Customer C ON R2.CustomerId = C.Id
    WHERE 
    (P.Disposition = 1 OR P.Disposition = 3) AND
    C.Name = '{}' AND R2.Id LIKE '{}%';
          """.format(
        customer, report_id
    )

    with creds.get_connection_pymssql() as conn:
        peak = pd.read_sql(sql=query, con=conn)
    return peak


# create new wind direction column
def _create_wind_direction(wind_N, wind_E):
    """
    Calculates wind direction based on northward and eastward wind speed components.

    Args:
        wind_N (Series): A pandas Series representing northward wind speeds.
        wind_E (Series): A pandas Series representing eastward wind speeds.

    Returns:
        list: A list of wind directions calculated from the northward and eastward components.
    """

    rotations = []
    for N, E in zip(list(wind_N), list(wind_E)):
        rotation = 90 + np.arctan2(-N, -E) * 180 / 3.14159
        rotations.append(rotation)
    return rotations


def _get_report_type(customer, creds, report_id):
    """
    Determines the type of report (emissions or compliance) for a given customer and report ID.

    Args:
        customer (str): The name of the customer.
        creds (CursorFactory): A CursorFactory instance with database credentials.
        report_id (str): The unique identifier for the report.

    Returns:
        DataFrame: A pandas DataFrame containing the description of the report type.
    """

    query = """
    SELECT RT.Description
    FROM Report R
    JOIN ReportType RT on R.ReportTypeId = RT.Id
    JOIN Customer C ON R.CustomerId = C.Id
    WHERE C.Name = '{}' AND R.Id LIKE '{}%';
                    """.format(
        customer, report_id
    )

    with creds.get_connection_pymssql() as conn:
        df_report_type = pd.read_sql(sql=query, con=conn)

    return df_report_type


def _get_report_fov3(creds, report_id, customer):
    """
    Retrieves the Field Of View (FOV3) spatial data for a given report.

    Args:
        creds (CursorFactory): A CursorFactory instance with database credentials.
        report_id (str): The unique identifier for the report.
        customer (str): The name of the customer associated with the report.

    Returns:
        DataFrame: A pandas DataFrame containing FOV3 spatial data for the specified report.
    """

    query = f"""
    SELECT R.Id
    ,R.ReportTitle
    ,R.DateStarted
    ,RFOVA.Shape.STAsText() as FOV3
    ,RFOVA.SurveyId
    FROM Report R
    INNER JOIN ReportFieldOfViewAggregated RFOVA on R.Id = RFOVA.ReportId
    JOIN Customer C ON R.CustomerId = C.Id
    WHERE C.Name = '{customer}' AND R.Id LIKE '{report_id}%';
         """

    with creds.get_connection_pymssql() as conn:
        df = pd.read_sql(sql=query, con=conn)
    return df


# Dynamo query
def _save_measurements(row):
    """
    Saves breadcrumb data associated with a survey into a pandas DataFrame.

    Args:
        row (Series): A pandas Series object representing a single row from a survey DataFrame.

    Returns:
        DataFrame: A pandas DataFrame containing the measurement data for the specified survey.
    """

    save_columns = [
        "ReportId",
        "CH4",
        "C2H6",
        "EpochTime",
        "GpsLongitude",
        "GpsLatitude",
        "CarSpeedNorth",
        "CarSpeedEast",
        "WindSpeedNorth",
        "WindSpeedEast",
        "WindSpeedLongitudinal",
        "WindSpeedLateral",
        "GpsFit",
    ]
    measurements_list = dynamo_dal.load_measurement_data(
        analyzer_id=row.AnalyzerId,
        start_epoch=row.StartEpoch,
        end_epoch=row.EndEpoch,
    )
    measurements = pd.DataFrame(measurements_list)
    measurements["ReportId"] = row.ReportId
    report_name = "cr-" + row.ReportId[:6]
    survey_name = row.SurveyId[:6]
    results = measurements[save_columns]
    return results


def _decrypt_disposition(df):
    """
    Replaces numerical disposition codes in a DataFrame with their corresponding textual descriptions.

    Args:
        df (DataFrame): A pandas DataFrame containing emission source data with numerical disposition codes.

    Returns:
        DataFrame: The input DataFrame with disposition codes replaced by their textual descriptions.
    """
    data_dict = {
        0: "Error",
        1: "Natural_Gas",
        2: "Not_Natural_Gas",
        3: "Possible_Natural_Gas",
        4: "Vehicle_Exhaust",
    }

    # Replace the values in the "Disposition" column using the data_dict
    df["Disposition"] = df["Disposition"].replace(data_dict)

    return df


def _process_dataframes(
    customer,
    report_id,
    cursor_factory,
    breadcrumbs,
    custom_gps_points,
    downsample_factor,
    emission_rate_threshold=2,
):
    """
    Fetches and preprocesses data from multiple sources to prepare for generating a comprehensive gas analytics report.
    This function serves multiple purposes:
    - Retrieves emissions source, peak emission, FOV3 (Field Of View), and breadcrumb data based on the specified customer
      and report ID.
    - Converts epoch times to datetime objects and adjusts them to the correct time zone.
    - Rounds numerical data to a specified number of decimal places for consistency.
    - Optionally filters breadcrumb data based on proximity to specified custom GPS points or significant emission sources
      to focus the analysis on areas of interest.

    Args:
        customer (str): The name of the customer for whom the report is being generated.
        report_id (str): The unique identifier for the report.
        cursor_factory (CursorFactory): A CursorFactory instance for database access.
        breadcrumbs (bool): Whether to include breadcrumb data in the report.
        custom_gps_points (bool/list): Either False or a list of dictionaries specifying custom GPS points to be included in the report.

    Returns:
        tuple: A tuple containing processed pandas DataFrames for emission sources, peaks, FOV3, and breadcrumbs.
    """

    time_zone = _get_timezone(report_id, customer, cursor_factory)

    report_es_df = _get_emissions_source(customer, report_id, cursor_factory)
    report_es_df["DateTime"] = pd.to_datetime(report_es_df["EpochTime"], unit="s")
    report_es_df = _convert_utc_to_timezone(report_es_df, "DateTime", time_zone)
    for col in report_es_df.select_dtypes(include=["float"]):
        if col not in ["GpsLongitude", "GpsLatitude"]:
            report_es_df[col] = report_es_df[col].round(3)
        else:
            report_es_df[col] = report_es_df[col].round(6)
    report_es_df = _decrypt_disposition(report_es_df)

    peaks_df = _get_peaks(cursor_factory, customer, report_id)
    peaks_df["DateTime"] = pd.to_datetime(peaks_df["EpochTime"], unit="s")
    peaks_df = _convert_utc_to_timezone(peaks_df, "DateTime", time_zone)
    peaks_df = _decrypt_disposition(peaks_df)

    fov3_df = _get_report_fov3(cursor_factory, report_id, customer)

    # Convert custom_gps_points to a GeoDataFrame and create buffers
    if custom_gps_points:
        custom_points_df = pd.DataFrame(custom_gps_points)
        gdf_points = gpd.GeoDataFrame(
            custom_points_df,
            geometry=gpd.points_from_xy(
                custom_points_df["longitude"], custom_points_df["latitude"]
            ),
        )

        # Set the CRS for WGS 84 (latitude and longitude)
        gdf_points.crs = "EPSG:4326"

        # Estimate the best UTM CRS based on the mean location
        utm_crs = gdf_points.estimate_utm_crs()

        # Convert the GeoDataFrame to the estimated UTM CRS
        gdf_points_utm = gdf_points.to_crs(utm_crs)

        # Apply a 50 meter buffer
        gdf_points_utm["buffer"] = gdf_points_utm.geometry.buffer(50)

        # Create a new GeoDataFrame from the buffer column
        buffer_gdf = gpd.GeoDataFrame(
            geometry=gdf_points_utm["buffer"], crs=gdf_points_utm.crs
        )

        # Convert this new GeoDataFrame to WGS 84
        buffer_gdf = buffer_gdf.to_crs("EPSG:4326")

        # Now, buffer_gdf contains the buffer geometries in WGS 84
        gdf_points["buffer"] = buffer_gdf.geometry

    elif breadcrumbs and not custom_gps_points:
        # Create GeoDataFrame from report_ES_df's longitude and latitude
        gdf_points = gpd.GeoDataFrame(
            report_es_df,
            geometry=gpd.points_from_xy(
                report_es_df["GpsLongitude"], report_es_df["GpsLatitude"]
            ),
        )

        # Set the CRS for WGS 84 (latitude and longitude)
        gdf_points.crs = "EPSG:4326"

        # Estimate the best UTM CRS based on the mean location
        utm_crs = gdf_points.estimate_utm_crs()

        # Convert the GeoDataFrame to the estimated UTM CRS
        gdf_points_utm = gdf_points.to_crs(utm_crs)

        # Apply a 50 meter buffer
        gdf_points_utm["buffer"] = gdf_points_utm.geometry.buffer(50).apply(
            lambda geom: geom.simplify(tolerance=0.5, preserve_topology=True)
        )

        # Create a new GeoDataFrame from the buffer column
        buffer_gdf = gpd.GeoDataFrame(
            geometry=gdf_points_utm["buffer"], crs=gdf_points_utm.crs
        )

        # Convert this new GeoDataFrame to WGS 84
        buffer_gdf = buffer_gdf.to_crs("EPSG:4326")

        # Now, buffer_gdf contains the buffer geometries in WGS 84
        gdf_points["buffer"] = buffer_gdf.geometry

    if breadcrumbs:
        breadcrumb_list = []
        surveys_df = _get_surveys_in_report(customer, report_id, cursor_factory)

        for index, row in surveys_df.iterrows():
            survey_breadcrumbs_df = _save_measurements(row)
            survey_breadcrumbs_df = _add_distance(survey_breadcrumbs_df)
            survey_breadcrumbs_gdf = gpd.GeoDataFrame(
                survey_breadcrumbs_df,
                geometry=gpd.points_from_xy(
                    survey_breadcrumbs_df["GpsLongitude"],
                    survey_breadcrumbs_df["GpsLatitude"],
                ),
            )

            filtered_breadcrumb_list = []

            # Filter emission sources to only include those with EmissionRate above a specific threshold (e.g., 5, the default value)
            # top_emission_buffers = gdf_points[gdf_points['EmissionRate'] > emission_rate_threshold]

            # Commented out the above, so we do not apply the filtering at all
            top_emission_buffers = gdf_points[gdf_points['EmissionRate'] > 0]
            
            num_emission_sources = (
                5 * downsample_factor
            )  # controls number of emission sources and breadcrumbs to display; may be completely ignored based on not applying filter buffer below ( for buffer in top_emission_buffers["buffer"]:)
            # Sort by 'EmissionRate' in descending order and select the top X entries
            top_emission_buffers = gdf_points.nlargest(
                num_emission_sources, "EmissionRate"
            )

            # Iterate over the filtered buffers
            for buffer in top_emission_buffers["buffer"]:
                # Filter survey_breadcrumbs_gdf for points within the current buffer
                # filtered_breadcrumbs = survey_breadcrumbs_gdf[
                #     survey_breadcrumbs_gdf.geometry.within(buffer)
                # ]
                # Commented out the above, so we do not apply the filtering at all
                filtered_breadcrumbs = survey_breadcrumbs_gdf
                filtered_breadcrumb_list.append(filtered_breadcrumbs)

            # survey_breadcrumbs_gdf = pd.concat(filtered_breadcrumbs).reset_index()
            survey_breadcrumbs_gdf = pd.concat(filtered_breadcrumb_list).reset_index()
            survey_breadcrumbs_gdf = survey_breadcrumbs_gdf.drop_duplicates(
                subset=["EpochTime", "GpsLongitude", "GpsLatitude"]
            )
            breadcrumb_list.append(survey_breadcrumbs_gdf)

        breadcrumb_df = pd.concat(breadcrumb_list).reset_index()
        breadcrumb_df["DateTime"] = pd.to_datetime(
            breadcrumb_df["EpochTime"].astype(float), unit="s"
        )
        breadcrumb_df = _convert_utc_to_timezone(breadcrumb_df, "DateTime", time_zone)
        breadcrumb_df["CH4"] = pd.to_numeric(breadcrumb_df["CH4"], errors="coerce")
        breadcrumb_df["WindSpeedNorth"] = pd.to_numeric(
            breadcrumb_df["WindSpeedNorth"], errors="coerce"
        )
        breadcrumb_df["WindSpeedEast"] = pd.to_numeric(
            breadcrumb_df["WindSpeedEast"], errors="coerce"
        )
        breadcrumb_df["wind_direction"] = _create_wind_direction(
            breadcrumb_df["WindSpeedNorth"], breadcrumb_df["WindSpeedEast"]
        )
        breadcrumb_df.sort_values(by="CH4", ascending=False, inplace=True)

    else:
        breadcrumb_df = None

    return report_es_df, peaks_df, fov3_df, breadcrumb_df


def _calculate_rolling_average(df, column_name, window_size):
    """
    Calculate the rolling average for a specified column in the DataFrame.

    :param df: DataFrame to calculate rolling average.
    :param column_name: Name of the column to calculate rolling average.
    :param window_size: Size of the rolling window.
    :return: DataFrame with rolling average.
    """
    df[f"{column_name}_rolling_avg"] = (
        df[column_name].rolling(window=window_size, min_periods=1).mean()
    )
    return df


def _downsample_dataframe(df, downsample_factor):
    """
    Downsample a DataFrame by a specific factor.

    :param df: DataFrame to downsample.
    :param downsample_factor: Factor by which to downsample (e.g., 10 for every 10th row).
    :return: Downsampled DataFrame.
    """
    # Select every 'downsample_factor'-th row in the DataFrame
    return df.iloc[::downsample_factor, :]


def _create_geodataframes(report_es_df, peaks_df, fov3_df, breadcrumb_df):
    """
    Converts pandas DataFrames into GeoPandas GeoDataFrames for spatial data processing and visualization.

    Args:
        report_es_df (DataFrame): DataFrame containing emission source data.
        peaks_df (DataFrame): DataFrame containing peak emission data.
        fov3_df (DataFrame): DataFrame containing FOV3 spatial data.
        breadcrumb_df (DataFrame): DataFrame containing breadcrumb data.

    Returns:
        tuple: A tuple of GeoPandas GeoDataFrames corresponding to the input pandas DataFrames.
    """

    report_es_gdf = gpd.GeoDataFrame(
        report_es_df,
        geometry=gpd.GeoSeries.from_wkt(report_es_df["EmissionSourceLisa"]),
    )
    peaks_gdf = gpd.GeoDataFrame(
        peaks_df,
        geometry=gpd.points_from_xy(peaks_df["Longitude"], peaks_df["Latitude"]),
    )
    fov3_gdf = gpd.GeoDataFrame(
        fov3_df, geometry=gpd.GeoSeries.from_wkt(fov3_df["FOV3"])
    )

    # Ensure the geometries are in a proper format
    report_es_gdf["geometry"] = report_es_gdf["geometry"].apply(
        lambda geom: geom if geom.is_valid else geom.buffer(0)
    )
    fov3_gdf["geometry"] = fov3_gdf["geometry"].apply(
        lambda geom: geom if geom.is_valid else geom.buffer(0)
    )

    if breadcrumb_df is not None:
        breadcrumb_gdf = gpd.GeoDataFrame(
            breadcrumb_df,
            geometry=gpd.points_from_xy(
                breadcrumb_df["GpsLongitude"], breadcrumb_df["GpsLatitude"]
            ),
        )
    else:
        breadcrumb_gdf = None

    report_es_gdf.crs = "EPSG:4326"
    peaks_gdf.crs = "EPSG:4326"
    fov3_gdf.crs = "EPSG:4326"

    return report_es_gdf, peaks_gdf, fov3_gdf, breadcrumb_gdf


def _initialize_map(fov3_gdf):
    """
    Initializes a Folium map centered on the geographic area covered by the FOV3 data.

    Args:
        fov3_gdf (GeoDataFrame): A GeoPandas GeoDataFrame containing FOV3 spatial data.

    Returns:
        Map: A Folium Map object.
    """

    if not fov3_gdf.empty and fov3_gdf["geometry"].notnull().any():
        centroid = fov3_gdf["geometry"].iloc[0].centroid
        mean_lat = centroid.y
        mean_lon = centroid.x
    else:
        mean_lat, mean_lon = 0, 0  # Fallback coordinates

    m = folium.Map(
        location=[mean_lat, mean_lon], zoom_start=18, max_zoom=22, tiles=None
    )
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="ESRI",
        name="ESRI World Imagery",
        max_zoom=22,
    ).add_to(m)

    return m


def _convert_datatypes(gdf):
    """
    Converts datatypes in a GeoDataFrame to types that are compatible with GeoPandas and spatial operations.

    Args:
        gdf (GeoDataFrame): The GeoPandas GeoDataFrame whose datatypes are to be converted.
    """

    if not gdf.empty:
        for col in gdf.select_dtypes(include=["datetime"]):
            gdf[col] = gdf[col].astype(str)

        for col in gdf.select_dtypes(include=["object"]):
            if len(gdf[col]) > 0 and isinstance(gdf[col].iloc[0], uuid.UUID):
                gdf[col] = gdf[col].astype(str)


def _format_value(value):
    """
    Formats a value to a standardized string representation, handling numeric values with two decimal places.

    Args:
        value: The value to be formatted.

    Returns:
        str: The formatted string representation of the input value.
    """

    try:
        float_value = float(value)
        return f"{float_value:.2f}"
    except ValueError:
        return value


def _add_popups(feature, **kwargs):
    """
    Creates a popup for a given feature on the map.

    Args:
        feature (dict): A dictionary representing the GeoJSON feature.
        **kwargs: Additional keyword arguments not used but necessary for compatibility.

    Returns:
        Popup: A folium.Popup object that can be added to a map object.
    """
    properties = feature["properties"]
    popup_content = "<br>".join(
        [f"{key}: {_format_value(value)}" for key, value in properties.items()]
    )
    return folium.Popup(popup_content)


def _add_geojson_to_map(
    gdf,
    map_object,
    style_function,
    include_tooltips=True,
    tooltip_fields=None,
    highlight_function=None,
):
    """
    Adds a GeoDataFrame as a GeoJSON layer to a folium map object.

    Args:
        gdf (GeoDataFrame): The geopandas GeoDataFrame to add to the map.
        map_object (Map): The folium map instance to which the GeoJSON layer will be added.
        style_function (function): A function used to style the GeoJSON layer.
        include_tooltips (bool, optional): If True, include tooltips on the GeoJSON objects. Defaults to True.
        tooltip_fields (list, optional): Fields to be included in the tooltips. Only used if include_tooltips is True.
        highlight_function (function, optional): A function used to style the GeoJSON layer when it is highlighted.

    Returns:
        None: The function directly modifies the map_object by adding a GeoJSON layer to it.
    """

    if not gdf.empty:
        # Validate and fix geometries if necessary
        gdf = gdf.copy()  # Create a copy to avoid modifying the original DataFrame

        if "buffer" in gdf.columns:
            gdf = gdf.drop(columns=["buffer"])

        gdf["geometry"] = gdf["geometry"].apply(
            lambda geom: geom if geom.is_valid else geom.buffer(0)
        )

        # Convert GeoDataFrame to GeoJSON
        geojson_data = gdf.to_json()

        if include_tooltips and tooltip_fields:
            tooltip = folium.features.GeoJsonTooltip(fields=tooltip_fields)
        else:
            tooltip = None

        folium.GeoJson(
            geojson_data,
            name="GeoJSON Layer",
            style_function=style_function,
            highlight_function=highlight_function,
            tooltip=tooltip,
        ).add_to(map_object)


def _add_circle_markers(gdf, map_object, radius, min_ch4, max_ch4, color_field=None):
    """
    Adds circle markers for each row in a GeoDataFrame to a folium map.

    Args:
        gdf (GeoDataFrame): The GeoDataFrame containing rows to represent as circle markers.
        map_object (Map): The folium map instance to which the circle markers will be added.
        radius (int): The radius of the circle markers.
        min_ch4 (float): The minimum value of CH4 to normalize the color scale.
        max_ch4 (float): The maximum value of CH4 to normalize the color scale.
        color_field (str, optional): The column name in gdf to base the marker color on. If None, a default color is used.

    Returns:
        None: The function directly modifies the map_object by adding circle markers to it.
    """

    for _, row in gdf.iterrows():
        if color_field and color_field in row:
            color = _get_color(row[color_field], min_ch4, max_ch4)
        else:
            color = "blue"
        folium.CircleMarker(
            location=[row["geometry"].y, row["geometry"].x],
            radius=radius,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=1,
            popup=folium.Popup(f"{row[color_field]}", max_width=450),
        ).add_to(map_object)


def _get_color(ch4_value, min_ch4, max_ch4):
    """
    Determines the color for a marker based on CH4 value using a predefined color scale.

    Args:
        ch4_value (float): The CH4 value for which to determine the marker color.
        min_ch4 (float): The minimum CH4 value of the scale.
        max_ch4 (float): The maximum CH4 value of the scale.

    Returns:
        str: The hex code of the color corresponding to the CH4 value.
    """

    # Define the colors for the colormap (e.g., green to red)
    colors = ["green", "yellow", "orange", "red", "darkred"]

    # Create a LinearSegmentedColormap with the defined colors
    colormap = LinearSegmentedColormap.from_list("custom_colormap", colors)

    # Normalize the CH4 value to the range [0, 1]
    norm = Normalize(vmin=min_ch4, vmax=max_ch4)

    if pd.isna(ch4_value):
        return "gray"  # Color for missing or NaN CH4 values
    else:
        # Convert ch4_value to float and normalize
        ch4_value_normalized = norm(float(ch4_value))
        return mcolors.to_hex(colormap(ch4_value_normalized))


def _process_dataframe_columns(df, exclude_rounding=None):
    """
    Processes DataFrame columns by converting object columns to numeric where possible and rounding float columns.

    Args:
        df (DataFrame): The pandas DataFrame to process.
        exclude_rounding (list, optional): List of column names to exclude from rounding operation.

    Returns:
        None: The function modifies the DataFrame in place.
    """

    if exclude_rounding is None:
        exclude_rounding = ["GpsLongitude", "GpsLatitude", "Latitude", "Longitude"]

    # Process object columns
    object_columns = [
        col
        for col in df.select_dtypes(include=["object"]).columns
        if col not in exclude_rounding
    ]
    for col in object_columns:
        # Check if the column can be converted to numeric
        if pd.to_numeric(df[col], errors="coerce").notna().all():
            df[col] = pd.to_numeric(df[col], errors="coerce")
        # Else, handle the column based on its specific data type or format

    # Round float columns
    round_columns = [
        col
        for col in df.select_dtypes(include=["float"]).columns
        if col not in exclude_rounding
    ]
    for col in round_columns:
        df[col] = df[col].round(3)

    for col in exclude_rounding:
        if col in df.columns:
            df[col] = df[col].round(6)


def _get_report_title(report_id, customer, creds):
    """
    Retrieves the title of a report based on the report ID and customer name.

    Args:
        report_id (str): The report's unique identifier.
        customer (str): The name of the customer.
        creds: Database credentials used to execute the query.

    Returns:
        DataFrame: A pandas DataFrame containing the report title.
    """

    query = f"""
    SELECT R.ReportTitle
    FROM Report R
    JOIN Customer C on C.Id = R.CustomerId
    WHERE R.Id LIKE '{report_id}%' AND C.Name = '{customer}';
    """

    with creds.get_connection_pymssql() as conn:
        df = pd.read_sql(sql=query, con=conn)
    return df


def _extract_emission_rate(report_title):
    """
    Extracts the emission rate from a report title using a regular expression.

    Args:
        report_title (str): The title of the report from which to extract the emission rate.

    Returns:
        str: The extracted emission rate as a string, including units. Returns 'Unknown' if not found.
    """
    # Regular expression pattern to find emission rate in the title
    pattern = r"(\d+\.?\d*)\s*scfh"
    match = re.search(pattern, report_title)
    if match:
        return match.group(0)  # Returns the emission rate with the unit 'scfh'
    else:
        return "Unknown"  # Return a default value or handle as needed


# Convert UTC Epoch time to datetime object
def _convert_epoch_to_utc(epoch_time):
    return datetime.utcfromtimestamp(epoch_time).replace(tzinfo=pytz.utc)


# Convert UTC datetime to a specific time zone
def _convert_utc_to_timezone(df, column_name, time_zone_str):
    """
    Converts UTC datetime objects in a DataFrame column to a specified time zone.

    Args:
        df (DataFrame): The pandas DataFrame containing the datetime objects.
        column_name (str): The name of the column containing the datetime objects.
        time_zone_str (str): The string representation of the target time zone.

    Returns:
        DataFrame: The DataFrame with the specified column converted to the target time zone.
    """

    time_zone_map = {
        "Pacific Standard Time": "US/Pacific",
        "Mountain Standard Time": "US/Mountain",
        "Central Standard Time": "US/Central",
        "Eastern Standard Time": "US/Eastern",
        "Atlantic Standard Time": "Canada/Atlantic",
        "Argentina Standard Time": "America/Argentina/Buenos_Aires",
        "GMT Standard Time": "GMT",
        "UTC": "UTC",
        "W. Europe Standard Time": "Europe/Berlin",
        "Central European Standard Time": "Europe/Paris",
        "E. Europe Standard Time": "Europe/Athens",
        "E. Africa Standard Time": "Africa/Nairobi",
        "Pakistan Standard Time": "Asia/Karachi",
        "Bangladesh Standard Time": "Asia/Dhaka",
        "SE Asia Standard Time": "Asia/Bangkok",
        "China Standard Time": "Asia/Shanghai",
        "Tokyo Standard Time": "Asia/Tokyo",
        "E. Australia Standard Time": "Australia/Sydney",
        "Central Pacific Standard Time": "Pacific/Guadalcanal",
        "New Zealand Standard Time": "Pacific/Auckland",
        "Hawaiian Standard Time": "Pacific/Honolulu",
        "Alaskan Standard Time": "US/Alaska",
    }
    target_time_zone = pytz.timezone(time_zone_map.get(time_zone_str, "UTC"))
    if column_name in df.columns:
        df[column_name] = (
            pd.to_datetime(df[column_name])
            .dt.tz_localize("UTC")
            .dt.tz_convert(target_time_zone)
        )
        df[column_name] = df[column_name].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df


def _create_svg_marker(angle, color, z_index=100, opacity=1):
    """
    Creates an SVG marker from scratch with a specified angle, color, z-index, and opacity.  This
    marker is used as the breadcrumb arrow.

    Args:
        angle (float): The rotation angle of the marker.
        color (str): The color of the marker.
        z_index (int, optional): The z-index of the marker, determining its stack order. Defaults to 100.
        opacity (float, optional): The opacity of the marker. Defaults to 1.

    Returns:
        str: An SVG string representing the marker.
    """
    return f"""
    <div style="z-index: {z_index};">
        <svg width="30" height="30" viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg" style="transform: rotate({angle}deg);">
            <!-- Arrow shaft -->
            <line x1="15" y1="22" x2="15" y2="10" style="stroke:{color};stroke-width:4; opacity:{opacity}" />
            <!-- Arrow head -->
            <polygon points="7,10 23,10 15,0" fill="{color}" style="opacity:{opacity}"/>
        </svg>
    </div>
    """


def _add_wind_direction_arrows(gdf, map_object, min_ch4, max_ch4, z_index=100):
    """
    Adds wind direction arrows to a folium map based on the wind direction data in a GeoDataFrame.

    Args:
        gdf (GeoDataFrame): The GeoDataFrame containing wind direction data.
        map_object (Map): The folium map instance to which the arrows will be added.
        min_ch4 (float): The minimum CH4 value used to normalize arrow colors.
        max_ch4 (float): The maximum CH4 value used to normalize arrow colors.
        z_index (int, optional): The z-index of the arrows, determining their stack order. Defaults to 100.

    Returns:
        None: The function directly modifies the map_object by adding wind direction arrows to it.
    """

    for index, row in gdf.iterrows():
        color = _get_color(row["CH4_rolling_avg"], min_ch4, max_ch4)
        angle = -row["wind_direction"]
        lat, lon = row["GpsLatitude"], row["GpsLongitude"]
        svg_marker = _create_svg_marker(angle, color, z_index)

        # Create the popup content
        #         popup_content = create_popup_content(row)
        #         popup = folium.Popup(popup_content, max_width=300)

        # Create the marker with the popup
        icon = folium.DivIcon(html=svg_marker)
        folium.Marker([lat, lon], icon=icon, pane="arrowPane").add_to(map_object)


#         folium.Marker([lat, lon], icon=icon,  pane='arrowPane', popup=popup).add_to(map_object)


def _create_popup_content(row):
    """
    Creates HTML content for a popup based on the data in a DataFrame row.

    Args:
        row (Series): A pandas Series object representing the row data.

    Returns:
        str: An HTML string representing the popup content.
    """

    # Customize the content with the data you want to show
    return f"""
        <div>
            <h4>Breadcrumb Details</h4>
            <p>CH4: {row['CH4']} ppm</p>
            <p>Latitude: {row['GpsLatitude']}</p>
            <p>Longitude: {row['GpsLongitude']}</p>
            <p>Time: {row['DateTime']}</p>
            <!-- Add more fields as needed -->
        </div>
    """


def _add_markers(
    gdf,
    map_object,
    marker_type,
    min_ch4=None,
    max_ch4=None,
    color_field=None,
    radius=3,
    popup_fields=None,
    z_index_offset=None,
    color="blue",
):
    """
    Adds markers to a folium map based on data in a GeoDataFrame.

    Args:
        gdf (GeoDataFrame): The GeoDataFrame containing the data for markers.
        map_object (Map): The folium map instance to which the markers will be added.
        marker_type (str): The type of marker to add ('circle' or 'point').
        min_ch4 (float, optional): The minimum CH4 value for color normalization.
        max_ch4 (float, optional): The maximum CH4 value for color normalization.
        color_field (str, optional): The column name to determine the marker color. If None, a default color is used.
        radius (int, optional): The radius of the circle markers.
        popup_fields (list, optional): A list of fields to display in the marker popup.
        z_index_offset (int, optional): The z-index offset for the markers, affecting their overlay order.

    Returns:
        None: The function directly modifies the map_object by adding markers to it.
    """

    for _, row in gdf.iterrows():
        location = [row["geometry"].y, row["geometry"].x]
        popup_content = (
            "<br>".join(
                [f"{field}: {row[field]}" for field in popup_fields if field in row]
            )
            if popup_fields
            else None
        )
        popup = folium.Popup(popup_content, max_width=450) if popup_content else None

        if color_field and color_field in row:
            color = (
                _get_color(row[color_field], min_ch4, max_ch4)
                if min_ch4 is not None and max_ch4 is not None
                else "blue"
            )

        marker_options = {
            "location": location,
            "radius": radius,
            "color": color,
            "fill": True,
            "fill_color": color,
            "fill_opacity": 1,
            "popup": popup,
        }

        # Add z_index_offset if provided
        if z_index_offset is not None:
            marker_options["z_index_offset"] = z_index_offset

        if marker_type == "circle":
            folium.CircleMarker(**marker_options).add_to(map_object)
        elif marker_type == "point":
            # Add other marker types as needed, for example, folium.Marker for simple points
            pass


def _create_colorbar_with_labels_base64(min_value, max_value, units="PPM"):
    """
    Creates a smaller colorbar with a semi-transparent background encoded as a base64 image.

    Args:
        min_value (float): The minimum value for the colorbar scale.
        max_value (float): The maximum value for the colorbar scale.
        units (str, optional): The units for the values on the colorbar. Defaults to 'PPM'.

    Returns:
        str: A base64 encoded string of the colorbar image.
    """

    colors = ["green", "yellow", "orange", "red", "darkred"]
    # Create a LinearSegmentedColormap
    colormap = LinearSegmentedColormap.from_list("custom_colormap", colors)

    # Create a scalar mappable object with the normalization and colormap
    norm = Normalize(vmin=min_value, vmax=max_value)
    scalar_mappable = plt.cm.ScalarMappable(norm=norm, cmap=colormap)
    scalar_mappable.set_array([])  # Set an empty array to initialize the ScalarMappable

    # Create a figure and a single subplot (ax) with reduced size
    fig, ax = plt.subplots(
        figsize=(0.5, 3.8)
    )  # Adjusted for vertical orientation and smaller size

    # Set figure background color with alpha (similar to legend's transparency)
    # fig.patch.set_facecolor((1, 1, 1, 0.8))  # White background with 80% opacity

    # Add color bar with annotations
    cbar = plt.colorbar(scalar_mappable, orientation="vertical", ax=ax)

    # Make colorbar labels bold
    for l in cbar.ax.yaxis.get_ticklabels():
        # l.set_weight('bold')
        l.set_color("black")
        l.set_fontsize(8)

    cbar.ax.text(
        0.5,
        1.05,
        units,
        va="bottom",
        ha="center",
        transform=cbar.ax.transAxes,
        color="black",
        fontsize=10,
    )

    # Remove the axes
    ax.remove()

    # Save the color bar image to a BytesIO object with semi-transparent background
    io_buffer = BytesIO()
    plt.savefig(
        io_buffer, format="png", bbox_inches="tight", pad_inches=0.02, transparent=True
    )
    plt.close()

    # Convert the BytesIO object to base64 string
    io_buffer.seek(0)
    base64_image = base64.b64encode(io_buffer.getvalue()).decode("utf-8")

    # Return the base64 string
    return f"data:image/png;base64,{base64_image}"


def _add_custom_gps_points(
    map_object, gps_points, marker_color="blue", popup_fields=None
):
    """
    Adds custom GPS points as markers on a folium map.

    Args:
        map_object (Map): The folium map instance to which the markers will be added.
        gps_points (list of dict): A list of dictionaries, each representing a GPS point with 'latitude' and 'longitude'.
        marker_color (str, optional): The color of the markers. Defaults to 'blue'.
        popup_fields (list, optional): A list of fields to include in the marker popups.

    Returns:
        None: The function directly modifies the map_object by adding custom GPS point markers to it.
    """

    for point in gps_points:
        location = [point["latitude"], point["longitude"]]
        popup_content = (
            "<br>".join(
                [f"{field}: {point[field]}" for field in popup_fields if field in point]
            )
            if popup_fields
            else None
        )
        popup = folium.Popup(popup_content, max_width=450) if popup_content else None

        folium.CircleMarker(
            location,
            radius=5,  # You can adjust the radius
            color=marker_color,
            fill=True,
            fill_color=marker_color,
            fill_opacity=1,
            popup=popup,
        ).add_to(map_object)


def _create_legend_html(
    fov_color="blue",
    peak_color="blue",
    lisa_color="orange",
    breadcrumb_color="green",
):
    """
    Generates HTML for a map legend with customizable colors for each symbol.

    Args:
        fov_color (str): Color for the FOV symbol (polygon).
        peak_color (str): Color for the peak symbol (circle).
        lisa_color (str): Color for the LISA symbol (polygon).
        breadcrumb_color (str): Color for the breadcrumb symbol (arrow).

    Returns:
        str: HTML string for the legend.
    """
    legend_html = f"""
        <div style="
            position: fixed; 
            bottom: 10px; left: 10px; width: 200px; height: 160px; 
            background-color: rgba(255, 255, 255, 0.8); 
            z-index:9999; font-size:14px;
            border:2px solid grey;
            padding: 10px;
        ">
            <b>Legend</b><br>
            <div style="margin-top: 10px;">
                <i style="background: {fov_color}; width: 20px; height: 10px; display: inline-block;"></i>
                &nbsp;FOV
            </div>
            <div style="margin-top: 10px;">
                <i style="background: {lisa_color}; width: 20px; height: 10px; display: inline-block;"></i>
                &nbsp;LISA
            </div>
            <div style="margin-top: 10px;">
                <i style="background: {peak_color}; border-radius: 50%; width: 10px; height: 10px; display: inline-block;"></i>
                &nbsp;Peak
            </div>
            <div style="margin-top: 10px;">
                <svg width="15" height="15" viewBox="0 0 30 30" xmlns="http://www.w3.org/2000/svg">
                    <!-- Arrow shaft -->
                    <line x1="15" y1="22" x2="15" y2="10" style="stroke:{breadcrumb_color};stroke-width:4;" />
                    <!-- Arrow head -->
                    <polygon points="7,10 23,10 15,0" fill="{breadcrumb_color}" />
                </svg>
                &nbsp;Breadcrumb
            </div>
        </div>
        """

    return legend_html


# todo - high C breadcrumbs on top
# todo - legend - preferably toggle layers


def _main():
    CUSTOMER = "Picarro"
    REPORT_ID = "a231a3a6"

    # alternate test
    # CUSTOMER = "Cadent"
    # REPORT_ID = "5ED0AD6C"

    custom_gps_points = [
        {
            "latitude": 37.42728033,
            "longitude": -122.07712867,
            "Location": "A",
            "Emission Rate": "0.02 scfh",
        }
        # You can add more points in this list
    ]

    m = view_report(CUSTOMER, REPORT_ID, custom_gps_points=False, breadcrumbs=True)
    return m


if __name__ == "__main__":
    _main()
