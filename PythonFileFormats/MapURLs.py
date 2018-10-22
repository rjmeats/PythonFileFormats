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

# Microsoft Bing maps. 
# https://msdn.microsoft.com/en-us/library/dn217138.aspx
# Styles are:
# - r = road view
# - a = aerial
# - h = aerial with labels
def urlForBingMaps(latitude, longitude, zoomLevel, style="r") :
    urlBase = "http://bing.com/maps/default.aspx"
    # Add URL parameters
    url = urlBase + "?" + "cp={0:f}~{1:f}&lvl={2:d}&style={3:s}".format(latitude, longitude, zoomLevel, style)
    return url

# Can also get Bing to put on a marker via the sp parameter (containing multiple values separated by underscores), but this also then displays
# a more detailed panel for the point waith title/notes and external links
#        maptitle="title"
#        mapnotes="Some notes"
#        mapurl="a url"
#        mapphoto="a photo url"
#        # a = aerial, can also be r for road, h= aerial with labels
#        bingparams = "cp={0:f}~{1:f}&lvl={2:d}&style=r&sp=point.{0:f}_{1:f}_{3:s}_{4:s}_{5:s}_{6:s}".format(latitude, longitude, zoomLevel, 
#                            maptitle, mapnotes, mapurl, mapphoto)
#        bingpinurl = "http://bing.com/maps/default.aspx?" + bingparams
