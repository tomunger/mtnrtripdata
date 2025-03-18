
from sqlalchemy import create_engine
from sqlalchemy import MetaData

import mtnschema

import mtndb

engine = create_engine("postgresql+psycopg://postgres:LetsClimb@localhost/newmountaineerdata", echo=True)
# engine = create_engine("sqlite://", echo=True)

mtn_db = mtndb.MtnDB(engine)

#mtn_db.drop_tables()
mtn_db.create_tables()

print ("done")