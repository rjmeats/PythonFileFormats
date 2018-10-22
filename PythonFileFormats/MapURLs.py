# Produce URLs linking to some common mapping systems

# Ordnance Survey free maps. NB Doesn't show a pin, so only shows the rough area related to the coordinates
# Determined by observation - no obvious online documentation of the URL parameters

def urlForOSMaps(latitude, longitude, zoomLevel) :
    urlBase = "https://osmaps.ordnancesurvey.co.uk"
    # Add parameters 
    url = urlBase + "/" + "{0:f},{1:f},{2:d}".format(latitude, longitude, zoomLevel)
    return url
