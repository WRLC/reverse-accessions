ALMA_SERVER = 'https://api-na.hosted.exlibrisgroup.com'

# These are read-only keys of all IZs that can be
# sources of linked accounts
SOURCE_IZ_KEYS = {
    '4617': 'apikey1',  # usually SCF
}

# Read write alma users api keys
IZ_READ_WRITE_KEYS = {
    '4102': 'apikey3',
    '4103': 'apikey4',
}

# Library, location, and policy info for destination IZ
DEFAULTS_IN_UPDATE_IZ = {
    '4102': {
              'library': 'librarycode',
              'libdesc': 'Library Description',
              'loc': 'locationcode',
              'ldesc': 'location description',
              'itempolicy': 'policycode',
              'idesc': 'policy description',
    },
    '4103': {
              'library': 'librarycode',
              'libdesc': 'Library Description',
              'loc': 'locationcode',
              'ldesc': 'location description',
              'itempolicy': 'policycode',
              'idesc': 'policy description',
    },
}
