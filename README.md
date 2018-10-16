# marblecutter-land-cover

This is a standalone (Python / Flask / WSGI) and Lambda-based dynamic tiler for
S3-hosted land cover GeoTIFFs.

## Development

A `docker-compose.yml` has been provided to facilitate development. To start the
web server, run:

```bash
docker-compose up
```

To start it in standalone mode, run:

```bash
docker-compose run --entrypoint bash marblecutter
```

## Deployment

When not using Lambda, `marblecutter-land-cover` is best managed using Docker. To
build an image, run:

```bash
make server
```

To start it, run:

```bash
docker run --env-file .env -p 8000:8000 quay.io/mojodna/marblecutter-tilezen
```

## Lambda Deployment

[Zappa](https://github.com/Miserlou/Zappa) is used to deploy
`marblecutter-land-cover` to AWS Lambda. To create an initial deployment:

```bash
cp zappa_settings.json.tpl zappa_settings.json
python3 -m venv venv
source venv/bin/activate
pip install -Ur requirements-zappa.txt
zappa deploy
```

`DATABASE_URL` must be set and pointed to a PostgreSQL instance with a
catalog loaded. This can either be set using `aws_environment_variables` in
`zappa_setting.json` or directly in Lambda (using the AWS console or command
line).

To update it, run:

```bash
zappa update
```

### Gotchas

The IAM role assumed by Lambda must have the
[AmazonS3ReadOnlyAccess](https://console.aws.amazon.com/iam/home?region=us-east-1#policies/arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess)
policy attached to it and access from target source buckets granted to the
account being used in order for data to be read.

## Colormaps

MODIS and ESACCI-LC sources have standard colormaps, as defined by legends
available elsewhere. These colormaps are not embedded in their respective
GeoTIFF sources, so they are defined as part of catalog metadata.

```python
# MODIS: IGBP Land Cover Classification colors
# ftp://ftp.glcf.umd.edu/glcf/Global_LNDCVR/Global_HD_Rev1/ASCII/IGBP_LndCvr_Lgnd_1000px.pdf
modis = {
    0: (69, 128, 162),  # "Water"
    1: (27, 119, 28),  # "Evergreen Needleleaf forest"
    2: (54, 136, 55),  # "Evergreen Broadleaf forest"
    3: (62, 171, 112),  # "Deciduous Needleleaf forest"
    4: (62, 168, 59),  # "Deciduous Broadleaf forest"
    5: (78, 156, 60),  # "Mixed forest"
    6: (173, 164, 127),  # "Closed shrublands"
    7: (205, 203, 164),  # "Open shrublands"
    8: (157, 180, 115),  # "Woody savannas"
    9: (192, 191, 95),  # "Savannas"
    10: (188, 212, 149),  # "Grasslands"
    11: (146, 184, 186),  # "Permanent wetlands"
    12: (215, 214, 114),  # "Croplands"
    13: (203, 8, 20),  # "Urban and built-up"
    14: (187, 226, 136),  # "Cropland/Natural vegetation mosaic"
    15: (195, 195, 205),  # "Snow and ice"
    16: (198, 180, 134),  # "Barren or sparsely vegetated"
    254: (0, 0, 0),  # "Unclassified"
    255: (0, 0, 0),  # "Fill Value"
}

# ESACCI-LC colors
# http://maps.elie.ucl.ac.be/CCI/viewer/download/ESACCI-LC-Legend.csv
esacci_lc = {
    10: (255, 255, 100),
    11: (255, 255, 100),
    12: (255, 255, 0),
    20: (170, 240, 240),
    30: (220, 240, 100),
    40: (200, 200, 100),
    50: (0, 100, 0),
    60: (0, 160, 0),
    61: (0, 160, 0),
    62: (170, 200, 0),
    70: (0, 60, 0),
    71: (0, 60, 0),
    72: (0, 80, 0),
    80: (40, 80, 0),
    81: (40, 80, 0),
    82: (40, 100, 0),
    90: (120, 130, 0),
    100: (140, 160, 0),
    110: (190, 150, 0),
    120: (150, 100, 0),
    121: (120, 75, 0),
    122: (150, 100, 0),
    130: (255, 180, 50),
    140: (255, 220, 210),
    150: (255, 235, 175),
    151: (255, 200, 100),
    152: (255, 210, 120),
    153: (255, 235, 175),
    160: (0, 120, 90),
    170: (0, 150, 120),
    180: (0, 220, 130),
    190: (195, 20, 0),
    200: (255, 245, 215),
    201: (220, 220, 220),
    202: (255, 245, 215),
    210: (0, 70, 200),
    220: (255, 255, 255),
}
```

## Classification correlation

Values for various land cover sources have been correlated according to the
following mapping. These mappings are defined as catalog recipes.

```python
nothing = 0
water = 10
developed = 20
barren = 30
forest = 40
shrubland = 50
herbaceous = 70
cultivated = 80
wetlands = 90
glacier = 100
desert = 110

# NLCD
# https://www.mrlc.gov/nlcd11_leg.php
nlcd = {
    11: water,  # Open Water
    12: glacier,  # Perennial Ice/Snow
    21: barren,  # Developed, Open Space
    22: developed,  # Developed, Low Intensity
    23: developed,  # Developed, Medium Intensity
    24: developed,  # Developed, High Intensity
    31: desert,  # Barren Land (Rock/Sand/Clay)
    41: forest,  # Deciduous Forest
    42: forest,  # Evergreen Forest
    43: forest,  # Mixed Forest
    51: shrubland,  # Dwarf Scrub
    52: shrubland,  # Shrub/Scrub
    71: herbaceous,  # Grassland/Herbaceous
    72: herbaceous,  # Sedge/Herbaceous
    73: herbaceous,  # Lichens
    74: herbaceous,  # Moss
    81: herbaceous,  # Pasture/Hay
    82: cultivated,  # Cultivated Crops
    90: wetlands,  # Woody Wetlands
    95: wetlands,  # Emergent Herbaceous Wetlands
}

nlcd_ak = {
    11: water,  # Open Water
    12: glacier,  # Perennial Ice/Snow
    21: barren,  # Developed, Open Space
    22: developed,  # Developed, Low Intensity
    23: developed,  # Developed, Medium Intensity
    24: developed,  # Developed, High Intensity
    31: barren,  # Barren Land (Rock/Sand/Clay)
    41: forest,  # Deciduous Forest
    42: forest,  # Evergreen Forest
    43: forest,  # Mixed Forest
    51: shrubland,  # Dwarf Scrub
    52: shrubland,  # Shrub/Scrub
    71: herbaceous,  # Grassland/Herbaceous
    72: herbaceous,  # Sedge/Herbaceous
    73: herbaceous,  # Lichens
    74: herbaceous,  # Moss
    81: herbaceous,  # Pasture/Hay
    82: cultivated,  # Cultivated Crops
    90: wetlands,  # Woody Wetlands
    95: wetlands,  # Emergent Herbaceous Wetlands
}

# C-CAP
# https://coast.noaa.gov/digitalcoast/training/ccap-land-cover-classifications.html
ccap = {
    2: developed,  # Developed, High Intensity
    3: developed,  # Developed, Medium Intensity
    4: developed,  # Developed, Low Intensity
    5: barren,  # Developed, Open Space
    6: cultivated,  # Cultivated Crops
    7: herbaceous,  # Pasture/Hay
    8: herbaceous,  # Grassland/Herbaceous
    9: forest,  # Deciduous Forest
    10: forest,  # Evergreen Forest
    11: forest,  # Mixed Forest
    12: shrubland,  # Scrub/Shrub
    13: wetlands,  # Palustrine Forested Wetland
    14: wetlands,  # Palustrine Scrub/Shrub Wetland
    15: wetlands,  # Palustrine Emergent Wetland (Persistent)
    16: wetlands,  # Estuarine Forested Wetland
    17: wetlands,  # Estuarine Scrub/Shrub Wetland
    18: wetlands,  # Estuarine Emergent Wetland
    19: desert,  # Unconsolidated Shore
    20: desert,  # Barren Land
    21: water,  # Open Water
    22: water,  # Palustrine Aquatic Bed
    23: water,  # Estuarine Aquatic Bed
    24: barren,  # Tundra
    25: glacier,  # Perennial Ice/Snow
}

# ESACCI-LC
# https://maps.elie.ucl.ac.be/CCI/viewer/download/CCI-LC_Maps_Legend.pdf
esacci_lc = {
    10: cultivated,  # Cropland, rainfed
    11: cultivated,  # Herbaceous cover
    12: cultivated,  # Tree or shrub cover
    20: cultivated,  # Cropland, irrigated or post-flooding
    30: cultivated,  # Mosaic cropland (>50%) / natural vegetation (tree, shrub, herbaceous cover) (<50%)
    40: cultivated,  # Mosaic natural vegetation (tree, shrub, herbaceous cover) (>50%) / cropland (<50%)
    50: forest,  # Tree cover, broadleaved, evergreen, closed to open (>15%)
    60: forest,  # Tree cover, broadleaved, deciduous, closed to open (>15%)
    61: forest,  # Tree cover, broadleaved, deciduous, closed (>40%)
    62: forest,  # Tree cover, broadleaved, deciduous, open (15‐40%)
    70: forest,  # Tree cover, needleleaved, evergreen, closed to open (>15%)
    71: forest,  # Tree cover, needleleaved, evergreen, closed (>40%)
    72: forest,  # Tree cover, needleleaved, evergreen, open (15‐40%)
    80: forest,  # Tree cover, needleleaved, deciduous, closed to open (>15%)
    81: forest,  # Tree cover, needleleaved, deciduous, closed (>40%)
    82: forest,  # Tree cover, needleleaved, deciduous, open (15‐40%)
    90: forest,  # Tree cover, mixed leaf type (broadleaved and needleleaved)
    100: shrubland,  # Mosaic tree and shrub (>50%) / herbaceous cover (<50%)
    110: herbaceous,  # Mosaic herbaceous cover (>50%) / tree and shrub (<50%)
    120: shrubland,  # Shrubland
    121: shrubland,  # Evergreen shrubland
    122: shrubland,  # Deciduous shrubland
    130: herbaceous,  # Grassland
    140: herbaceous,  # Lichens and mosses
    150: barren,  # Sparse vegetation (tree, shrub, herbaceous cover) (<15%)
    151: barren,  # Sparse tree (<15%)
    152: barren,  # Sparse shrub (<15%)
    153: barren,  # Sparse herbaceous cover (<15%)
    160: wetlands,  # Tree cover, flooded, fresh or brackish water
    170: wetlands,  # Tree cover, flooded, saline water
    180: wetlands,  # Shrub or herbaceous cover, flooded, fresh/saline/brackish water
    190: developed,  # Urban areas
    200: desert,  # Bare areas
    201: desert,  # Consolidated bare areas
    202: desert,  # Unconsolidated bare areas
    210: water,  # Water bodies
    220: glacier,  # Permanent snow and ice
}

esacci_lc_mid_lat = {
    10: cultivated,  # Cropland, rainfed
    11: cultivated,  # Herbaceous cover
    12: cultivated,  # Tree or shrub cover
    20: cultivated,  # Cropland, irrigated or post-flooding
    30: cultivated,  # Mosaic cropland (>50%) / natural vegetation (tree, shrub, herbaceous cover) (<50%)
    40: cultivated,  # Mosaic natural vegetation (tree, shrub, herbaceous cover) (>50%) / cropland (<50%)
    50: forest,  # Tree cover, broadleaved, evergreen, closed to open (>15%)
    60: forest,  # Tree cover, broadleaved, deciduous, closed to open (>15%)
    61: forest,  # Tree cover, broadleaved, deciduous, closed (>40%)
    62: forest,  # Tree cover, broadleaved, deciduous, open (15‐40%)
    70: forest,  # Tree cover, needleleaved, evergreen, closed to open (>15%)
    71: forest,  # Tree cover, needleleaved, evergreen, closed (>40%)
    72: forest,  # Tree cover, needleleaved, evergreen, open (15‐40%)
    80: forest,  # Tree cover, needleleaved, deciduous, closed to open (>15%)
    81: forest,  # Tree cover, needleleaved, deciduous, closed (>40%)
    82: forest,  # Tree cover, needleleaved, deciduous, open (15‐40%)
    90: forest,  # Tree cover, mixed leaf type (broadleaved and needleleaved)
    100: shrubland,  # Mosaic tree and shrub (>50%) / herbaceous cover (<50%)
    110: herbaceous,  # Mosaic herbaceous cover (>50%) / tree and shrub (<50%)
    120: shrubland,  # Shrubland
    121: shrubland,  # Evergreen shrubland
    122: shrubland,  # Deciduous shrubland
    130: herbaceous,  # Grassland
    140: herbaceous,  # Lichens and mosses
    150: barren,  # Sparse vegetation (tree, shrub, herbaceous cover) (<15%)
    151: barren,  # Sparse tree (<15%)
    152: barren,  # Sparse shrub (<15%)
    153: barren,  # Sparse herbaceous cover (<15%)
    160: wetlands,  # Tree cover, flooded, fresh or brackish water
    170: wetlands,  # Tree cover, flooded, saline water
    180: wetlands,  # Shrub or herbaceous cover, flooded, fresh/saline/brackish water
    190: developed,  # Urban areas
    200: barren,  # Bare areas
    201: barren,  # Consolidated bare areas
    202: barren,  # Unconsolidated bare areas
    210: water,  # Water bodies
    220: glacier,  # Permanent snow and ice
}

# MODIS Land Cover
# http://glcf.umd.edu/data/lc/
modis = {
    0: water,  # "Water"
    1: forest,  # "Evergreen Needleleaf forest"
    2: forest,  # "Evergreen Broadleaf forest"
    3: forest,  # "Deciduous Needleleaf forest"
    4: forest,  # "Deciduous Broadleaf forest"
    5: forest,  # "Mixed forest"
    6: shrubland,  # "Closed shrublands"
    7: shrubland,  # "Open shrublands"
    8: herbaceous,  # "Woody savannas"
    9: herbaceous,  # "Savannas"
    10: herbaceous,  # "Grasslands"
    11: wetlands,  # "Permanent wetlands"
    12: cultivated,  # "Croplands"
    13: developed,  # "Urban and built-up"
    14: cultivated,  # "Cropland/Natural vegetation mosaic"
    15: glacier,  # "Snow and ice"
    16: desert,  # "Barren or sparsely vegetated"
    254: nothing,  # "Unclassified"
    255: nothing,  # "Fill Value"
}
```