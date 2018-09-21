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

Docker is required to create `deps/deps.tgz`, which contains binary dependencies
and Python packages built for the Lambda runtime.

### Up

[Up](https://github.com/apex/up) uses CloudFormation to deploy and manage Lambda
functions and API Gateway endpoints. It bundles a reverse proxy so that standard
web services can be deployed.

```bash
make deploy-up
```

### Gotchas

The IAM role assumed by Lambda (created by Up) must have the
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
    10: (255, 100),
    11: (255, 100),
    12: (255, 0),
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

# NLCD
# https://www.mrlc.gov/nlcd11_leg.php
nlcd = {
    11: water,
    12: water,
    21: developed,
    22: developed,
    23: developed,
    24: developed,
    31: barren,
    41: forest,
    42: forest,
    43: forest,
    51: shrubland,
    52: shrubland,
    71: herbaceous,
    72: herbaceous,
    73: herbaceous,
    74: herbaceous,
    81: cultivated,
    82: cultivated,
    90: wetlands,
    95: wetlands,
}

# ESACCI-LC
# https://maps.elie.ucl.ac.be/CCI/viewer/download/CCI-LC_Maps_Legend.pdf
esacci_lc = {
    10: cultivated,
    11: cultivated,
    12: cultivated,
    20: cultivated,
    30: cultivated,
    40: cultivated,
    50: forest,
    60: forest,
    61: forest,
    62: forest,
    70: forest,
    71: forest,
    72: forest,
    80: forest,
    81: forest,
    82: forest,
    90: forest,
    100: shrubland,
    110: herbaceous,
    120: shrubland,
    121: shrubland,
    122: shrubland,
    130: herbaceous,
    140: herbaceous,
    150: barren,
    151: barren,
    152: barren,
    153: barren,
    160: wetlands,
    170: wetlands,
    180: wetlands,
    190: developed,
    200: barren,
    201: barren,
    202: barren,
    210: water,
    220: water,
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
    15: water,  # "Snow and ice"
    16: barren,  # "Barren or sparsely vegetated"
    254: nothing,  # "Unclassified"
    255: nothing,  # "Fill Value"
}
```