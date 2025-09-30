import datetime
import re
from selenium import webdriver
from sqlalchemy import create_engine

import mtndb
import mtnweb
import econfig

YEAR_FIRST_DATE_PAT = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
DAY_FIRST_DASH_DATE_PAT = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
DAY_FIRST_SLASH_DATE_PAT = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
YEAR_FIRST_DATE = "%Y-%m-%d"
DAY_FIRST_DASH_DATE = "%m-%d-%Y"
DAY_FIRST_SLASH_DATE = "%m/%d/%Y"

def parse_date(date_str: str) -> datetime.date:
    M = YEAR_FIRST_DATE_PAT.match(date_str)
    if M:
        date = datetime.datetime.strptime(date_str, YEAR_FIRST_DATE).date()
        return date
    M = DAY_FIRST_DASH_DATE_PAT.match(date_str)
    if M:
        date = datetime.datetime.strptime(date_str, DAY_FIRST_DASH_DATE).date()
        return date
    M = DAY_FIRST_SLASH_DATE_PAT.match(date_str)
    if M:
        date = datetime.datetime.strptime(date_str, DAY_FIRST_SLASH_DATE).date()
        return date
    raise ValueError(f"Unrecognized date string: {date_str}")




def make_mtnweb(is_visible: bool = True) -> mtnweb.ScrapeMtnWeb:
    options = webdriver.FirefoxOptions()
    options.binary_location = econfig.get(econfig.FIREFOX_PATH)
    if not is_visible: 
        options.add_argument("-headless")
    driver = webdriver.Firefox(options=options)
    mtn_web = mtnweb.ScrapeMtnWeb(driver)
    return mtn_web


def make_mtndb(is_echo: bool = False) -> mtndb.MtnDB:
    engine = create_engine(econfig.get(econfig.DATABASE_URL), echo=is_echo)
    mtn_db = mtndb.MtnDB(engine)
    return mtn_db


def make_neo4j_db():
    """Create Neo4j database connection using environment credentials."""
    import neo4j_db
    return neo4j_db.Neo4jDB()
