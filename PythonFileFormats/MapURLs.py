# Produce URLs linking to some common mapping systems

# Zoom level definitions, seems to be shared by different map providers
# https://wiki.openstreetmap.org/wiki/Zoom_levels

# Ordnance Survey free maps. NB Doesn't show a pin, so only shows the rough area related to the coordinates
# Determined by observation - no obvious online documentation of the URL parameters
def urlForOrdnanceSurveyMaps(latitude, longitude, zoomLevel) :
    urlBase = "https://osmaps.ordnancesurvey.co.uk"
    # Add 'parameters' (not really presented as URL paramters, just comma-separated additions to the path)
    url = urlBase + "/" + "{0:f},{1:f},{2:d}".format(latitude, longitude, zoomLevel)
    return url


# OpenStreetMap maps. Includes a pin at the mlat/mlon point
# Reference: https://wiki.openstreetmap.org/wiki/Browsing#Sharing_a_link_to_the_maps
def urlForOpenStreetMaps(latitude, longitude, zoomLevel) :
    urlBase = "https://www.openstreetmap.org"
    # Add URL parameters 
    url = urlBase + "/" + "?" + "&mlat={0:f}&mlon={1:f}#map={2:d}/{0:f}/{1:f}".format(latitude, longitude, zoomLevel)
    return url

# Google maps. Includes a pin.
# https://developers.google.com/maps/documentation/urls/guide
def urlForGoogleMaps(latitude, longitude, zoomLevel) :
    urlBase = "https://www.google.com/maps/search"
    # Add URL parameters
    url = urlBase + "/" + "?" + "api=1&query={0:f}%2C{1:f}&zoom={2:d}".format(latitude, longitude, zoomLevel)
    return url

# Alternative Google maps, doesn't include a pin, but allows type of map to vary. basemap values allowed are:
# - satellite
# - roadmap
# - terrain
# https://developers.google.com/maps/documentation/urls/guide
def urlForGoogleMaps2(latitude, longitude, zoomLevel, basemap="satellite") :
    urlBase = "https://www.google.com/maps"
    # Add URL parameters
    url = urlBase + "/" + "@?" + "api=1&map_action=map&center={0:f}%2C{1:f}&zoom={2:d}&basemap={3:s}".format(latitude, longitude, zoomLevel, basemap)
    return url

# Alternative Google maps, doesn't include a pin, but allows type of map to vary. basemap values allowed are:
# - satellite
# - roadmap
# - terrain
# https://developers.google.com/maps/documentation/urls/guide
def urlForGoogleMapsStreetView(latitude, longitude) :
    urlBase = "https://www.google.com/maps"
    # Add URL parameters
    url = urlBase + "/" + "@?" + "api=1&map_action=pano&viewpoint={0:f}%2C{1:f}".format(latitude, longitude)
    return url
