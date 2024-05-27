import ee
import ast
import json
import folium
import pandas as pd
import tensorflow as tf

from datetime import datetime
from dateutil.relativedelta import relativedelta
from google.oauth2.service_account import Credentials


# Define the required scopes
scopes = ['https://www.googleapis.com/auth/earthengine.readonly',
          'https://www.googleapis.com/auth/cloud-platform']

# Load the service account credentials with the defined scopes
credentials = Credentials.from_service_account_file(
    'data/ee-nadhifn1261-db50f2bd6754.json', scopes=scopes)

# Use these credentials to authenticate
ee.Initialize(credentials)

f = open('data/indonesia.geojson')
geojson = f.read()
f.close()

geojson = json.loads(geojson)
geojson_featureCollection = ee.FeatureCollection(geojson).filter('state == "Kalimantan Barat"')


def get_data(geojson_featureCollection):
    # Define the final date as the first day of the current month at midnight
    final_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # Define the initial date as exactly 3 months before the final date at midnight
    initial_date = final_date - relativedelta(months=3)
    initial_date = initial_date.replace(hour=0, minute=0, second=0, microsecond=0)

    temp_list_data = []
    current_date = initial_date
    error_list = []

    while current_date < final_date:
        print('Processing on date: ', current_date)

        try:
            image_collection = (
                ee.ImageCollection('MODIS/061/MOD21C3')
                .filterBounds(geojson_featureCollection)
                .filterDate(current_date)
                .select('LST_Day')
            )

            image_list = image_collection.getRegion(geometry=geojson_featureCollection, scale=1000).getInfo()

            temp_list_data.append(image_list)
        except:
            error_list.append(current_date.strftime('%Y-%m-%d'))
            print('Error on date: ', current_date.strftime('%Y-%m-%d'))
            exit()

        current_date += relativedelta(months=1)

    return temp_list_data


def list_to_df(list_data):
    list = []
    coordinate = [str(item[1:3]) for item in list_data[0]]

    for day in range(len(list_data)):
        daily_data = list_data[day]
        temp_list = [item[-1] for item in daily_data]
        list.append(temp_list)

    # Convert the list of lists into a DataFrame
    result_df = pd.DataFrame(list, columns=coordinate)
    result_df.drop(result_df.columns[0], axis=1, inplace=True)

    return result_df


def clean_df(df):
    df = df.dropna(axis=1, how='all')
    df = df.interpolate(method='linear')
    df = df.bfill()
    if df.isna().sum().sum() == 0:
        print('Data cleaning success')
        return df
    else:
        print('Data cleaning failed')
        # stop the program
        exit()


def predict(df):
    index_list = list(df.columns.values)
    index_list = [ast.literal_eval(string) for string in index_list]

    model = tf.keras.models.load_model('models/model_1_3.keras')

    x_pred = df.transpose().values
    y_pred = model.predict(x_pred)

    pred_df = pd.DataFrame(index_list, columns=['longitude', 'latitude'])
    pred_df['surface_temp'] = y_pred

    # Convert the temperature from Kelvin to Celsius
    pred_df['surface_temp'] = pred_df['surface_temp'] - 273.15

    # Filter the data with surface temperature above 35 degrees Celsius
    pred_df = pred_df[pred_df['surface_temp'] >= 35]

    return pred_df


def create_map(pred_df):
    map_center = [pred_df['latitude'].mean(), pred_df['longitude'].mean()]
    m = folium.Map(location=map_center, zoom_start=9)

    for index, row in pred_df.iterrows():
        folium.Circle([row['latitude'], row['longitude']],
                      radius=10,
                      color='red',  # fixed color for all markers
                      weight=1,
                      fill=True,
                      fill_color='red',  # fixed fill color for all markers
                      fill_opacity=0.4).add_to(m)

    m.save('index.html')
    print('Done!')


list_data = get_data(geojson_featureCollection)
df = list_to_df(list_data)
df = clean_df(df)
pred_df = predict(df)
create_map(pred_df)
