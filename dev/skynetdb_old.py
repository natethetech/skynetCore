from peewee import *

database = MySQLDatabase('skynetCore', **{'host': '192.168.1.252', 'password': 'skynet', 'port': 3306, 'user': 'node'})

class UnknownField(object):
    def __init__(self, *_, **__): pass

class BaseModel(Model):
    class Meta:
        database = database

class HvacPollStatuses(BaseModel):
    status = CharField()
    statusid = BigIntegerField(db_column='statusID', primary_key=True)

    class Meta:
        db_table = 'hvac_poll_statuses'

class HvacSystemEventtypes(BaseModel):
    eventname = CharField(db_column='eventName')
    eventtypeid = BigIntegerField(db_column='eventTypeID', primary_key=True)

    class Meta:
        db_table = 'hvac_system_eventTypes'

class ThermVendors(BaseModel):
    vendorid = BigIntegerField(db_column='vendorID', primary_key=True)
    vendorname = CharField(db_column='vendorName', unique=True)

    class Meta:
        db_table = 'therm_vendors'

class ThermZones(BaseModel):
    floor = IntegerField()
    zoneid = BigIntegerField(db_column='zoneID', primary_key=True)
    zonelongname = CharField(db_column='zoneLongName')
    zonename = CharField(db_column='zoneName', unique=True)

    class Meta:
        db_table = 'therm_zones'

class ThermUnits(BaseModel):
    thermalunitid = BigIntegerField(db_column='thermalUnitID', primary_key=True)
    unitname = CharField(db_column='unitName')
    unitsymbol = CharField(db_column='unitSymbol')

    class Meta:
        db_table = 'therm_units'

class ThermPollers(BaseModel):
    ip_address = CharField()
    pollerid = BigIntegerField(db_column='pollerId', primary_key=True)
    pollername = CharField(db_column='pollerName', index=True)
    thermalunitid = ForeignKeyField(db_column='thermalUnitID', rel_model=ThermUnits, to_field='thermalunitid')
    vendorid = ForeignKeyField(db_column='vendorID', rel_model=ThermVendors, to_field='vendorid')
    zoneid = ForeignKeyField(db_column='zoneID', rel_model=ThermZones, to_field='zoneid')

    class Meta:
        db_table = 'therm_pollers'
        indexes = (
            (('zoneid', 'thermalunitid'), False),
        )

class ThermTempreadings(BaseModel):
    pollerid = ForeignKeyField(db_column='pollerID', rel_model=ThermPollers, to_field='pollerid')
    tempid = BigIntegerField(db_column='tempID', primary_key=True)
    temperature = FloatField()

    class Meta:
        db_table = 'therm_tempReadings'

class HvacSystemUnits(BaseModel):
    unitid = BigIntegerField(db_column='unitID', primary_key=True)
    unitlongname = CharField(db_column='unitLongName')
    unitname = CharField(db_column='unitName')

    class Meta:
        db_table = 'hvac_system_units'

class HvacSystemEvents(BaseModel):
    eventid = BigIntegerField(db_column='eventID', primary_key=True)
    eventtypeid = ForeignKeyField(db_column='eventTypeID', rel_model=HvacSystemEventtypes, to_field='eventtypeid')
    tempid = ForeignKeyField(db_column='tempID', rel_model=ThermTempreadings, to_field='tempid')
    unitid = ForeignKeyField(db_column='unitID', rel_model=HvacSystemUnits, to_field='unitid')

    class Meta:
        db_table = 'hvac_system_events'
        indexes = (
            (('unitid', 'eventtypeid', 'tempid'), False),
        )

class HvacSystemStatus(BaseModel):
    polldate = DateField(db_column='pollDate')
    pollid = BigIntegerField(db_column='pollID', primary_key=True)
    statusid = ForeignKeyField(db_column='statusID', rel_model=HvacPollStatuses, to_field='statusid')
    unitid = ForeignKeyField(db_column='unitID', rel_model=HvacSystemUnits, to_field='unitid')

    class Meta:
        db_table = 'hvac_system_status'

