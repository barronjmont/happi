"""
PyMongo Backend Implementation
"""
import logging

from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure

from .core import Backend
from ..errors import DatabaseError, SearchError, DuplicateError

logger = logging.getLogger(__name__)


class MongoBackend(metaclass=Backend):
    """
    Abstraction for MongoDB backend

    Parameters
    ----------
    host : str, optional
        Hostname for MongoDB

    user : str, optional
        Username for MongoDB instance

    pw :str, optional
        Password for given username

    host : str, optional
        Host of the MongoDB instance

    db : str, optional
        Database name within the MongoDB instance

    timeout : float, optional
        Time to wait for connection attempt
    """
    _timeout = 5
    _conn_str = 'mongodb://{user}:{pw}@{host}/{db}'  # String for login

    def __init__(self, host=None, user=None,
                 pw=None, db=None, collection=None,
                 timeout=None):
        # Default timeout
        timeout = timeout or self._timeout
        # Format connection string
        conn_str = self._conn_str.format(user=user, pw=pw,
                                         host=host, db=db)
        logging.debug('Attempting connection using %s ', conn_str)
        self._client = MongoClient(conn_str, serverSelectionTimeoutMS=timeout)
        self._db = self._client[db]
        # Load collection
        try:
            if collection not in self._db.collection_names():
                raise DatabaseError('Unable to locate collection {} '
                                    'in database'.format(collection))
            self._collection = self._db[collection]
        # Unable to view collection names
        except OperationFailure as e:
            raise PermissionError(e)
        # Unable to connect to MongoDB instance
        except ServerSelectionTimeoutError:
            raise DatabaseError('Unable to connect to MongoDB instance, check '
                                'that the server is running on the host and '
                                'port specified at startup')

    @property
    def all_devices(self):
        """
        List of all device sub-dictionaries
        """
        return self._collection.find()

    def find(self, multiples=False, **kwargs):
        """
        Find an instance or instances that matches the search criteria

        Parameters
        ----------
        multiples : bool
            Find a single result or all results matching the provided
            information

        kwargs :
            Requested information
        """
        # Find all matches
        cur = list(self._collection.find(kwargs))
        # Only return a single device if requested
        if not multiples:
            # Grab first item
            try:
                cur = cur[0]
            # If no items were returned
            except IndexError:
                logger.debug("No items found when searching for multiples")
        return cur

    def save(self, _id, post, insert=True):
        """
        Save information to the database

        Parameters
        ----------
        _id : str
            ID of device

        post : dict
            Information to place in database

        insert : bool, optional
            Whether or not this a new device to the database

        Raises
        ------
        DuplicateError:
            If insert is True, but there is already a device with the provided
            _id

        SearchError:
            If insert is False, but there is no device with the provided _id

        PermissionError:
            If the write operation fails due to issues with permissions
        """
        try:
            # Add to database
            result = self._collection.update_one({'_id': _id},
                                                 {'$set': post},
                                                 upsert=insert)
        except OperationFailure:
            raise PermissionError("Unauthorized command, make sure you are "
                                  "using a user with write permissions")

        if insert and not result.upserted_id:
            raise DuplicateError('Device with id {} has already been entered '
                                 'into the database, use load_device and '
                                 'save if you wish to make changes to the '
                                 'device'.format(_id))

        if not insert and result.matched_count == 0:
            raise SearchError('No device found with id {} please, if this is '
                              'a new device, try add_device. If not, make '
                              'sure that the device information being sent is '
                              'correct'.format(_id))

    def delete(self, _id):
        """
        Delete a device instance from the database

        Parameters
        ----------
        _id : str
            ID of device
        """
        self._collection.delete_one({'_id': _id})
