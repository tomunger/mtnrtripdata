# Configuration

Configuration is by environment variables.  These can be put in a file and loaded on the command line with `-C`.

Example


    DATABASE_URL=postgresql+psycopg://postgres:LetsClimb@localhost/mountaineerdata

    MTN_WEB_URL=https://www.mountaineers.org/

    MTN_WEB_USERNAME=tkunger
    MTN_WEB_PASSWORD=exexex

    BROWSER=firefox
    FIREFOX_PATH=/Applications/Firefox.app/Contents/MacOS/firefox
    
## DATABASE_URL

An SQLAlchemy database URL

## MTN_WEB_URL

The mountaineers web site.

## MTN_WEB_USERNAME and MTN_WEB_PASSWORD

Your user name and password

# BROWSER and FIREFOX_PATH

Currently, the only `BROWSER` supported is `firefox`.  So you need to provide the `FIREFOX_PATH`


