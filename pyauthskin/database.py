import tortoise
from tortoise.models import Model
from tortoise import fields

class User(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=255, unique=True)
    password = fields.CharField(max_length=255)

class Player(Model):
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField('models.User', related_name='players')
    name = fields.CharField(max_length=255)
    uuid = fields.CharField(max_length=255, unique=True)
    skin_texture = fields.ForeignKeyField('models.Texture', related_name='skin_players', null=True)
    cape_texture = fields.ForeignKeyField('models.Texture', related_name='cape_players', null=True)

class Texture(Model):
    id = fields.IntField(pk=True)
    # Allow multiple Texture records to share the same file hash so that
    # different users can each have their own Texture DB entry pointing to
    # the same physical file. Uniqueness is managed at the file path level
    # instead of the DB hash field.
    hash = fields.CharField(max_length=255)
    path = fields.CharField(max_length=255)
    uploader = fields.ForeignKeyField('models.User', related_name='textures', null=True)
    width = fields.IntField(default=64)
    height = fields.IntField(default=64)
    display_name = fields.CharField(max_length=255, default="")
    model = fields.CharField(max_length=10, default="classic")  # classic or slim