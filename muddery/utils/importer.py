"""
This module handles importing data from files to models.
"""

import os
import csv
from django.db import models
from django.db.models.loading import get_model
from django.conf import settings
from evennia.utils import logger
from muddery.utils.exception import MudderyError


def import_csv(file_name, model_name):
    """
    Import data from a csv file to the db model

    Args:
        file_name: (string) CSV file's name.
        app_name: (string) Db app's name.
        model_name: (string) Db model's name.
    """
    try:
        # load file
        csvfile = open(file_name, 'r')
        reader = csv.reader(csvfile)

        # get model
        model_obj = get_model(settings.WORLD_DATA_APP, model_name)

        # clear old data
        model_obj.objects.all().delete()

        # read title
        title = reader.next()

        # get field types
        # type = 0    means common field
        # type = 1    means ForeignKey field
        # type = 2    means ManyToManyField field, not support
        # type = -1   means field does not exist

        field_types = []
        related_fields = []
        for field_name in title:
            field_type = -1
            related_field = 0

            try:
                # get field info
                field = model_obj._meta.get_field(field_name)

                if isinstance(field, models.ForeignKey):
                    field_type = 1
                    related_field = field.related_field
                elif isinstance(field, models.ManyToManyField):
                    field_type = 2
                else:
                    field_type = 0
            except Exception, e:
                logger.log_errmsg("Field error: %s" % e)

            field_types.append(field_type)
            related_fields.append(related_field)

        # import values
        # read next line
        values = reader.next()
        while values:
            try:
                record = {}
                for item in zip(title, field_types, values, related_fields):
                    field_name = item[0]
                    field_type = item[1]
                    value = item[2]
                    related_field = item[3]

                    # set field values
                    if field_type == 0:
                        record[field_name] = value
                    elif field_type == 1:
                        arg = {}
                        arg[related_field.name] = value
                        record[field_name] = related_field.model.objects.get(**arg)

                # create new record
                data = model_obj.objects.create(**record)
                data.save()
            except Exception, e:
                logger.log_errmsg("Can't load data: %s" % e)

            # read next line
            values = reader.next()

    except StopIteration:
        # reach the end of file, pass this exception
        pass


def import_file(file_name, model_name):
    """
    Import data from a data file to the db model

    Args:
        file_name: (string) Data file's name.
        model_name: (string) Db model's name.
    """

    file_type = settings.WORLD_DATA_FILE_TYPE.lower()
    if file_type == "csv":
        import_csv(file_name, model_name)
    else:
        message = "Does not support file type %s" % settings.WORLD_DATA_FILE_TYPE
        raise MudderyError(message)


def import_all():
    """
    Import all data files to models.
    """

    # count the number of files loaded
    count = 0

    # get model name
    model_name_list = [model for data_models in settings.WORLD_DATA_MODELS
                       for model in data_models]

    # get file's extension name
    file_type = settings.WORLD_DATA_FILE_TYPE.lower()
    ext_name = ""
    if file_type == "csv":
        ext_name = ".csv"
    else:
        message = "Does not support file type %s" % settings.WORLD_DATA_FILE_TYPE
        raise MudderyError(message)

    # import models one by one
    for model_name in model_name_list:
        # make file name
        file_name = os.path.join(settings.GAME_DIR, settings.WORLD_DATA_FOLDER, model_name + ext_name)

        # import data
        try:
            if file_type == "csv":
                import_csv(file_name, model_name)

            ostring = "%s imported" % model_name
            print ostring

            count += 1
        except Exception, e:
            ostring = "Can not import %s: %s" % (model_name, e)
            print ostring
            continue

    ostring = "Total %d files imported.\n" % count
    print ostring
