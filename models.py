import tortoise
from tortoise.models import Model
from tortoise import fields

class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=255, unique=True)
    password = fields.CharField(max_length=255)
    uuid = fields.CharField(max_length=255, unique=True)

class Texture(Model):
    id = fields.IntField(pk=True)
    hash = fields.CharField(max_length=255, unique=True)
    path = fields.CharField(max_length=255)
    uploader = fields.ForeignKeyField('models.User', related_name='uploaded_textures', null=True)

class UserTexture(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField('models.User', related_name='textures')
    texture = fields.ForeignKeyField('models.Texture', related_name='users')
    display_name = fields.CharField(max_length=255)
    is_active_skin = fields.BooleanField(default=False)
    is_active_cape = fields.BooleanField(default=False)