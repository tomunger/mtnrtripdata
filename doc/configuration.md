# Configuration

Configuration is by environment variables.  These can be put in a file and loaded on the command line with `-C`.

Example


    DATABASE_URL=postgresql+psycopg://postgres:LetsClimb@localhost/mountaineerdata


    NEO4J_URL=bolt://localhost:9012
    NEO4J_USERNAME=neo4j
    NEO4J_PASSWORD=LetsClimb


    MTN_WEB_URL=https://www.mountaineers.org/
    MTN_WEB_USERNAME=tkunger
    MTN_WEB_PASSWORD=...

    BROWSER=firefox
    FIREFOX_PATH=/Applications/Firefox.app/Contents/MacOS/firefox
    
## DATABASE_URL

An SQLAlchemy database URL

## NEO4J

Configure access to the neo4j database.  See [postgres.yaml](../deploy/postgres.yaml)

## MTN_WEB_URL

The mountaineers web site.

## MTN_WEB_USERNAME and MTN_WEB_PASSWORD

Your user name and password

# BROWSER and FIREFOX_PATH

Currently, the only `BROWSER` supported is `firefox`.  So you need to provide the `FIREFOX_PATH`


