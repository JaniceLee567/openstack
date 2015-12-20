

class Driver(object):
    """Base class for all ServiceGroup drivers."""
    
    def join(self, member, group, service=None):
        """Add a new member to a service group.
        
        :param member: the joined member ID/name 
        :param group: the group ID/name, of the joined member 
        :param service£ºa 'nova.service.Service' object
        """
        
        raise NotImplementedError()
    
    def is_up(self, member):
        """check whether the given member is up. """
        raise NotImplementedError()