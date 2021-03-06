"""
This is adapt from evennia/evennia/objects/objects.py.
The licence of Evennia can be found in evennia/LICENSE.txt.

MudderyObject is an object which can load it's data automatically.

"""

import json
import ast
from django.conf import settings
from django.db.models.loading import get_model
from evennia.objects.objects import DefaultObject
from evennia.utils import logger
from evennia.utils.utils import make_iter
from muddery.utils import utils


class MudderyObject(DefaultObject):
    """
    This object loads attributes from world data on init automatically.
    """

    def at_init(self):
        """
        Load world data.
        """
        super(MudderyObject, self).at_init()

        # need save before modify m2m fields
        self.save()

        try:
            self.load_data()
        except Exception, e:
            logger.log_errmsg("%s can not load data:%s" % (self.dbref, e))


    def at_object_receive(self, moved_obj, source_location):
        """
        Called after an object has been moved into this object.

        Args:
            moved_obj (Object): The object moved into this one
            source_location (Object): Where `moved_object` came from.

        """
        # Call hook on source location
        if source_location:
            source_location.at_object_left(moved_obj, moved_obj.location)


    def at_object_left(self, moved_obj, target_location):
        """
        Called after an object has been removed from this object.
        
        Args:
        moved_obj (Object): The object leaving
        target_location (Object): Where `moved_obj` is going.
        
        """
        pass
    
    
    def set_data_info(self, model, key):
        """
        Set data_info's model and key. It puts info into attributes.
            
        Args:
            model: (string) Db model's name.
            key: (string) Key of the data info.
        """
        utils.set_obj_data_info(self, model, key)


    def get_data_record(self):
        """
        Get object's data record from database.
        """
        # Get model and key names.
        model = self.attributes.get(key="model", category=settings.WORLD_DATA_INFO_CATEGORY, strattr=True)
        if not model:
            return
        
        key = self.attributes.get(key="key", category=settings.WORLD_DATA_INFO_CATEGORY, strattr=True)
        if not key:
            return
        
        # Get db model
        model_obj = get_model(settings.WORLD_DATA_APP, model)
        if not model_obj:
            raise MudderyError("%s can not open model %s" % (key, model))
        
        # Get data record.
        data = model_obj.objects.filter(key=key)
        if not data:
            raise MudderyError("%s can not find key %s" % (key, key))
        
        return data[0]


    def load_data(self):
        """
        Set data_info to the object."
        """
        data = self.get_data_record()
        if not data:
            return

        self.set_typeclass(data.typeclass)
        self.set_name(data.name)
        self.set_alias(data.alias)
        self.set_location(data.location)
        self.set_home(data.home)
        self.set_desc(data.desc)
        self.set_lock(data.lock)
        self.set_attributes(data.attributes)


    def set_typeclass(self, typeclass):
        """
        Set object's typeclass.
        
        Args:
        typeclass: (string) Typeclass's name.
        """
        if not typeclass:
            typeclass = settings.BASE_OBJECT_TYPECLASS
    
        if self.is_typeclass(typeclass, exact=True):
            # No change.
            return
    
        if not hasattr(self, 'swap_typeclass'):
            logger.log_errmsg("%s cannot have a type at all!" % self.get_info_key())
            return
    
        self.swap_typeclass(typeclass, clean_attributes=False)


    def set_name(self, name):
        """
        Set object's name.
        
        Args:
        name: (string) Name of the object.
        """
        if name == self.name:
            # No change.
            return
    
        self.name = name

        # we need to trigger this here, since this will force
        # (default) Exits to rebuild their Exit commands with the new
        # aliases
        #self.at_cmdset_get(force_init=True)

        if self.destination:
            self.flush_from_cache()


    def set_alias(self, aliases):
        """
        Set object's alias.
        
        Args:
        aliases: (string) Aliases of the object.
        """
        # merge the old and new aliases (if any)
        new_aliases = [alias.strip().lower() for alias in aliases.split(';')
                       if alias.strip()]

        set_new_aliases = set(new_aliases)
        set_current_aliases = set(self.aliases.all())
                   
        if set_new_aliases == set_current_aliases:
            # No change.
            return

        self.aliases.clear()
        self.aliases.add(new_aliases)
    
        # we need to trigger this here, since this will force
        # (default) Exits to rebuild their Exit commands with the new
        # aliases
        #self.at_cmdset_get(force_init=True)
    
        if self.destination:
            self.flush_from_cache()


    def set_location(self, location):
        """
        Set object's location.
        
        Args:
        location: (string) Location's name. Must be the key of data info.
        """
        location_obj = None
    
        if location:
            # If has location, search location object.
            location_obj = utils.search_obj_info_key(location)

            if not location_obj:
                logger.log_errmsg("%s can't find location %s!" % (self.get_info_key(), location))
                return
        
            location_obj = location_obj[0]
    
        if self.location == location_obj:
            # No change.
            return

        if self == location_obj:
            # Can't set location to itself.
            logger.log_errmsg("%s can't teleport itself to itself!" % self.get_info_key())
            return
    
        # try the teleport
        self.move_to(location_obj, quiet=True, to_none=True)


    def set_home(self, home):
        """
        Set object's home.
        
        Args:
        home: (string) Home's name. Must be the key of data info.
        """
        home_obj = None
    
        if home:
            # If has home, search home object.
            home_obj = utils.search_obj_info_key(home)
        
            if not home_obj:
                logger.log_errmsg("%s can't find home %s!" % (self.get_info_key(), home))
                return
            
            home_obj = home_obj[0]
    
        if self.home == home_obj:
            # No change.
            return

        if self == home_obj:
            # Can't set home to itself.
            logger.log_errmsg("%s can't set home to itself!" % self.get_info_key())
            return
        
        self.home = home_obj


    def set_desc(self, desc):
        """
        Set object's description.
        
        Args:
        desc: (string) Description.
        """
        self.db.desc = desc


    def set_lock(self, lock):
        """
        Set object's lock.
        
        Args:
        lock: (string) Object's lock string.
        """
        if lock:
            try:
                self.locks.add(lock)
            except Exception:
                logger.log_errmsg("%s can't set lock %s." % (self.get_info_key(), lock))


    def set_attributes(self, attributes):
        """
        Set object's attribute.
        
        Args:
        attributes: (string) Attribues in form of python dict. Such as: "{'age':'22', 'career':'warrior'}"
        """
        if not attributes:
            return
        
        # Set attributes.
        attr = {}
        try:
            # Convert string to dict
            attributes = ast.literal_eval(attributes)
        except Exception, e:
            logger.log_errmsg("%s can't load attributes %s: %s" % (self.get_info_key(), attributes, e))
    
        for key in attr:
            # Add attributes.
            try:
                self.attributes.add(key, attr[key])
            except Exception:
                logger.log_errmsg("%s can't set attribute %s!" % (self.get_info_key(), key))


    def set_obj_destination(self, destination):
        """
        Set object's destination
        
        Args:
        destination: (string) Destination's name. Must be the key of data info.
        """
        destination_obj = None
    
        if destination:
            # If has destination, search destination object.
            destination_obj = utils.search_obj_info_key(destination)
        
        if not destination_obj:
            logger.log_errmsg("%s can't find destination %s!" % (self.get_info_key(), destination))
            return
        
        destination_obj = destination_obj[0]
    
        if obj.destination == destination_obj:
            # No change.
                return

        if self == destination_obj:
            # Can't set destination to itself.
            logger.log_errmsg("%s can't set destination to itself!" % self.get_info_key())
            return
    
        self.destination = destination_obj


    def set_detail(self, key, detail):
        """
        Set object's detail.
        
        Args:
        key: (string) Detail's key.
        detail: (string) Detail's info.
        """
        pass


    def get_info_key(self):
        """
        Get data info's key.
        """
        key = self.attributes.get(key="key", category=settings.WORLD_DATA_INFO_CATEGORY, strattr=True)
        if not key:
            key = ""
        return key


    def get_surroundings(self, caller):
        """
        This is a convenient hook for a 'look'
        command to call.
        """
        pass


    def get_appearance(self, caller):
        """
        This is a convenient hook for a 'look'
        command to call.
        """
        # get name and description
        info = {"dbref": self.dbref,
                "name": self.name,
                "desc": self.db.desc,
                "cmds": self.get_available_commands(caller)}
                
        return info
            
            
    def get_available_commands(self, caller):
        """
        This returns a list of available commands.
        "args" must be a string without ' and ", usually it is self.dbref.
        """
        # commands = [{"name":"LOOK", "cmd":"look", "args":self.dbref}]
        commands = []
        return commands


    def msg(self, text=None, from_obj=None, sessid=0, **kwargs):
        """
        Emits something to a session attached to the object.
        
        Args:
        text (str, optional): The message to send
        from_obj (obj, optional): object that is sending. If
        given, at_msg_send will be called
        sessid (int or list, optional): sessid or list of
        sessids to relay to, if any. If set, will
        force send regardless of MULTISESSION_MODE.
        Notes:
        `at_msg_receive` will be called on this Object.
        All extra kwargs will be passed on to the protocol.
        
        """
        raw = kwargs.get("raw", False)
        if not raw:
            try:
                text = json.dumps(text)
            except Exception, e:
                text = json.dumps({"err": "There is an error occurred while outputing messages."})
                logger.log_errmsg("json.dumps failed: %s" % e)

        # set raw=True
        if kwargs:
            kwargs["raw"] = True
        else:
            kwargs = {"raw": True}

        if from_obj:
            # call hook
            try:
                from_obj.at_msg_send(text=text, to_obj=self, **kwargs)
            except Exception:
                log_trace()
        try:
            if not self.at_msg_receive(text=text, **kwargs):
                # if at_msg_receive returns false, we abort message to this object
                return
        except Exception:
            log_trace()
                                                        
        # session relay
        kwargs['_nomulti'] = kwargs.get('_nomulti', True)

        if self.player:
            # for there to be a session there must be a Player.
            if sessid:
                sessions = make_iter(self.player.get_session(sessid))
            else:
                # Send to all sessions connected to this object
                sessions = [self.player.get_session(sessid) for sessid in self.sessid.get()]
            if sessions:
                sessions[0].msg(text=text, session=sessions, **kwargs)
