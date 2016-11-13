#!/usr/bin/python

from peewee import *

database = MySQLDatabase('skynetCore-primitive', **{'host': '192.168.1.252', 'password': 'skynet', 'port': 3306, 'user': 'skynet'})

class UnknownField(object):
    def __init__(self, *_, **__): pass

class BaseModel(Model):
    class Meta:
        database = database

class SystemStatus(BaseModel):
    lastchanged = DateTimeField(db_column='lastChanged', null=True)
    unitname = CharField(db_column='unitName', primary_key=True)
    unitstatus = IntegerField(db_column='unitStatus')

    class Meta:
        db_table = 'system_status'



database.connect()
element = SystemStatus.get(SystemStatus.unitname=="HEAT")
print element.unitname
