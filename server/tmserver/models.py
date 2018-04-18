from datetime import datetime
import re

import bcrypt
import peewee as pw

from . import config

BAD_USERNAME_CHARS_RE = re.compile(r'[\:\'";%]')
MIN_PASSWORD_LEN = 12

class GameObjectManager:
    # TODO do i actually want this? i think i do since while area_of_effect
    # could live in UserAccount, this class will also be handling creating and
    # destroying contain relationships. Those methods might should go into
    # Contains, though. I'll keep this here for now until more dust settles.
    def area_of_effect(self, user_account):
        """Given a user_account, returns the set of objects that should
        receive events the account emits.
        """
        # We want a set that includes:
        # - the user_account's player object
        # - objects that contain that player object
        # - objects contained by player object
        # - objects contained by objects that contain the player object
        #
        # these four categories can, for the most part, correspond to:
        # - a player of the game
        # - the room a player is in
        # - the player's inventory
        # - objects in the same room as the player
        #
        # thought experiment: the bag
        #
        # my player object has been put inside a bag. The bag _contains_ my
        # player object, and is in a way my "room." it's my conceit that
        # whatever thing contains that bag should not receive the events my
        # player object generates.
        #
        # this is easier to implement and also means you can "muffle" an object
        # by stuffing it into a box.
        inventory = set(self.player_object.contains)
        room = set(self.player_object.contained_by)
        adjacent_objs = set(room.contains)
        return {self.player_object} & inventory & room & adjacent_objs


    # TODO it's arguable these should be defined on Contains
    def put_into(outer_obj, inner_obj):
        Contains.create(outer_obj=outer_obj, inner_obj=inner_obj)

    def remove_from(outer_obj, inner_obj):
        Contains.delete().where(
            Contains.outer_obj==outer_obj,
            Contains.inner_obj==inner_obj).execute()


class BaseModel(pw.Model):
    # TODO is it chill to just add created/updated meta fields here?
    class Meta:
        database = config.get_db()

class UserAccount(BaseModel):
    """This model represents the bridge between the game world (a big tree of
    objects) and a live conncetion from a game client. A user account doesn't
    "exist," per se, in the game world, but rather is anchored to a single
    "player" object. this player object is the useraccount's window on the game
    world."""
    username = pw.CharField(unique=True)
    display_name = pw.CharField(default='a gaseous cloud')
    password = pw.CharField()
    # TODO add metadata -- created at and updated at

    def hash_password(self):
        self.password = bcrypt.hashpw(self.password.encode('utf-8'), bcrypt.gensalt())

    def check_password(self, plaintext_password):
        return bcrypt.checkpw(plaintext_password.encode('utf-8'), self.password.encode('utf-8'))

    # TODO should this be a class method?
    def validate(self):
        if 0 != len(UserAccount.select().where(UserAccount.username == self.username)):
            raise Exception('username taken: {}'.format(self.username))

        if BAD_USERNAME_CHARS_RE.search(self.username):
            raise Exception('username has invalid character')

        if len(self.password) < MIN_PASSWORD_LEN:
            raise Exception('password too short')

    def init_player_obj(self, description=''):
        return GameObject.create(
            author=self,
            name=self.display_name,
            description=description,
            is_player_obj=True)

    @property
    def player_obj(self):
        gos = GameObject.select().where(
            GameObject.author==self,
            GameObject.is_player_obj==True)
        if gos:
            return gos[0]
        return None


class Script(BaseModel):
    author = pw.ForeignKeyField(UserAccount)

class ScriptRevision(BaseModel):
    code = pw.TextField()
    script = pw.ForeignKeyField(Script)

class GameObject(BaseModel):
    # every object needs to tie to a user account for authorizaton purposes
    author = pw.ForeignKeyField(UserAccount)
    name = pw.CharField()
    description = pw.TextField()
    script_revision = pw.ForeignKeyField(ScriptRevision, null=True)
    is_player_obj = pw.BooleanField(default=False)

    def contains(self):
        return (c.inner_obj for c in Contains.select().where(Contains.outer_obj==self))

    def contained_by(self):
        model_set = list(Contains.select().where(Contains.inner_obj==self))
        if not model_set:
            # TODO uhh
            pass
        if len(model_set) > 1:
            # TODO uhh
            pass
        return model_set[0]

    @property
    def user_account(self):
        if self.is_player_obj:
            return self.author
        return None

class Contains(BaseModel):
    outer_obj = pw.ForeignKeyField(GameObject)
    inner_obj = pw.ForeignKeyField(GameObject)


class Log(BaseModel):
    env = pw.CharField()
    created_at = pw.DateTimeField(default=datetime.utcnow())
    level = pw.CharField()
    raw = pw.CharField()


MODELS = [UserAccount, Log, GameObject, Contains, Script, ScriptRevision]
