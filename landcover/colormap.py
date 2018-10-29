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

COLORMAP = {
    # paint nothing as water; this happens after source merging, so overlap isn't a concern
    nothing: (69, 128, 162),
    water: (69, 128, 162),
    forest: (27, 119, 28),
    shrubland: (184, 193, 112),
    herbaceous: (188, 212, 149),
    wetlands: (146, 184, 186),
    cultivated: (215, 214, 114),
    developed: (203, 8, 20),
    barren: (198, 180, 134),
    glacier: (230, 239, 253),
    desert: (232, 211, 157),
}
