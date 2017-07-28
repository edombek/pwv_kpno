#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

#    This file is part of the pwv_kpno software package.
#
#    The pwv_kpno package is free software: you can redistribute it and/or
#    modify it under the terms of the GNU General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    The pwv_kpno package is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with pwv_kpno.  If not, see <http://www.gnu.org/licenses/>.

"""This document defines end user functions for the pwv_kpno package.
It relies heavily on the atmospheric transmission models generated by
create_atm_models.py and the modeled PWV level at Kitt Peak generated by
create_pwv_models.py. Functions contained in this document include
`available_data`, `update_models`, `measured_pwv`, `modeled_pwv`,
and `transmission`.
"""

import os
import glob
import pickle
from datetime import datetime, timedelta

import numpy as np
from pytz import utc
from astropy.table import Table
from scipy.interpolate import interpn

from .create_pwv_models import _update_suomi_data
from .create_pwv_models import _update_pwv_model

__author__ = 'Daniel Perrefort'
__copyright__ = 'Copyright 2017, Daniel Perrefort'
__credits__ = ['Alexander Afanasyev', 'Micahel Wood-Vasey']

__license__ = 'GPL V3'
__email__ = 'djperrefort@gmail.com'
__status__ = 'Development'


# Define necessary directory paths
FILE_DIR = os.path.dirname(os.path.realpath(__file__))
ATM_MOD_DIR = os.path.join(FILE_DIR, 'atm_models')  # atmospheric models
PWV_TAB_DIR = os.path.join(FILE_DIR, 'pwv_tables')  # PWV data tables


def _timestamp(date):
    """Returns seconds since epoch of a UTC datetime in %Y-%m-%dT%H:%M format

    This function provides compatability for Python 2.7, for which the
    datetime.timestamp method was not yet available.

    Args:
        date_str (str): Datetime as string in %Y-%m-%dT%H:%M format
    """

    unix_epoch = datetime(1970, 1, 1, tzinfo=utc)
    utc_date = date.astimezone(utc)
    timestamp = (utc_date - unix_epoch).total_seconds()
    return timestamp


def available_data():
    """Return a list of years for which SuomiNet data has been downloaded

    Return a list of years for which SuomiNet data has been downloaded to the
    local machine. Note that this list includes years for which any amount
    of data has been downloaded. It does not indicate if additional data has
    been released by SuomiNet for a given year that is not locally available.

    Args:
        None

    Returns:
        years (list): A list of years with locally available SuomiNet data
    """

    config_path = os.path.join(FILE_DIR, 'CONFIG.txt')
    with open(config_path, 'rb') as ofile:
        years = list(pickle.load(ofile))
        years.sort()
        return years


def update_models(year=None):
    """Download data from SuomiNet and update the locally stored PWV model

    Update the locally available SuomiNet data by downloading new data from
    the SuomiNet website. Use this data to create an updated model for the PWV
    level at Kitt Peak. If a year is provided, only update data for that year.
    If not, download all available data from 2017 onward. Data for years from
    2010 through 2016 is included with this package version by default.

    Args:
        year (int): A Year from 2010 onward

    Returns:
        updated_years (list): A list of years for which models where updated
    """

    # Check for valid args
    if not (isinstance(year, int) or year is None):
        raise TypeError("Argument 'year' must be an integer")

    if isinstance(year, int):
        if year < 2010:
            raise ValueError('Cannot update models for years prior to 2010')

        elif year > datetime.now().year:
            msg = 'Cannot update models for years greater than current year'
            raise ValueError(msg)

    # Update the local SuomiData and PWV models
    updated_years = _update_suomi_data(year)
    _update_pwv_model()

    return updated_years


def _check_search_args(year, month, day, hour):
    """This function provides argument type and value checking

    This function provides argument type and value checking for the functions
    `measured_pwv` and `modeled_pwv`.

    Args:
        year  (int): An integer value betwean 2010 and the current year
        month (int): An integer value betwean 0 and 12
        day   (int): An integer value betwean 0 and 31
        hour  (int): An integer value betwean 0 and 24

    Returns:
        None
    """

    if not (isinstance(year, int) or year is None):
        raise TypeError("Argument 'year' (pos 1) must be an integer")

    elif isinstance(year, int) and year < 2010:
        raise ValueError('pwv_kpno does not provide data years prior to 2010')

    elif isinstance(year, int) and year > datetime.now().year:
        raise ValueError("Argument 'year' (pos 1) is larger than current year")

    def check_type(arg, value, pos, bound):
        """Check an argument is of an appropriate type and value"""

        if not (isinstance(value, int) or value is None):
            msg = "Argument '{0}' (pos {1}) must be an integer"
            raise TypeError(msg.format(arg, pos))

        if isinstance(value, int) and not (0 < value < bound):
            raise ValueError('Invalid value for {0}: {1}'.format(arg, value))

    check_type('month', month, 2, 13)
    check_type('day', day, 3, 32)
    check_type('hour', hour, 4, 25)


def _search_dt_table(data_tab, **params):
    """Search an astropy table

    Given an astropy table with column 'date', return all entries in the table
    for which there is an object in date with attributes matching the values
    specified in params

    Args:
        data_tab (astropy.table.Table): An astropy table to search
        **params (): The parameters to search data_tab for

    Returns:
        Entries from data_tab that match search parameters
    """

    # Credit for this function belongs to Alexander Afanasyev
    # https://codereview.stackexchange.com/questions/165811

    def vectorize_callable(item):
        """Checks if datetime attributes match specified values"""
        return all(getattr(item, param_name) == param_value
                   for param_name, param_value in params.items()
                   if param_value is not None)

    indexing_func = np.vectorize(vectorize_callable)
    return data_tab[np.where(indexing_func(data_tab['date']))[0]]


def measured_pwv(year=None, month=None, day=None, hour=None):
    """Return an astropy table of PWV measurements taken by SuomiNet

    Return an astropy table of precipitable water vapor (PWV) measurements
    taken by the SuomiNet project. The first column is named 'date' and
    contains the UTC datetime of each measurement. Successive columns are
    named using the SuomiNet IDs for different locations and contain PWV
    measurements for that location in millimeters. By default the returned
    table contains all locally available SuomiNet data. Results can be
    refined by year, month, day, and hour by using the keyword arguments.

    Args:
        year  (int): The year of the desired PWV data
        month (int): The month of the desired PWV data
        day   (int): The day of the desired PWV data
        hour  (int): The hour of the desired PWV data in 24-hour format

    Returns:
        data (astropy.table.Table): A table of measured PWV values in mm
    """

    # Check for valid arguments
    _check_search_args(year, month, day, hour)

    # Read in SuomiNet measurements from the master table
    data = Table.read(os.path.join(PWV_TAB_DIR, 'measured_pwv.csv'))

    # Convert UNIX timestamps to UTC
    data['date'] = np.vectorize(datetime.utcfromtimestamp)(data['date'])
    data['date'].unit = 'UTC'

    # Assign units to the remaining columns
    for colname in data.colnames:
        if colname != 'date':
            data[colname].unit = 'mm'

    # Refine results to only include datetimes indicated by kwargs
    return _search_dt_table(data, year=year, month=month, day=day, hour=hour)


def modeled_pwv(year=None, month=None, day=None, hour=None):
    """Return an astropy table of the modeled PWV at Kitt Peak

    Return a model for the precipitable water vapor level at Kitt Peak as an
    astropy table. The first column of the table is named 'date' and contains
    the UTC datetime of each modeled value. The second column is named 'pwv',
    and contains PWV values in millimeters. By default this function returns
    modeled values from 2010 onward. Results can be restricted to a specific
    year, month, day, and hour by using the key word arguments.

    Args:
        year  (int): The year of the desired PWV data
        month (int): The month of the desired PWV data
        day   (int): The day of the desired PWV data
        hour  (int): The hour of the desired PWV data in 24-hour format

    Returns:
        data (astropy.table.Table): A table of modeled PWV values in mm
    """

    # Check for valid arg types
    _check_search_args(year, month, day, hour)

    # Read in SuomiNet measurements from the master table
    data = Table.read(os.path.join(PWV_TAB_DIR, 'modeled_pwv.csv'))

    # Convert UNIX timestamps to UTC
    data['date'] = np.vectorize(datetime.utcfromtimestamp)(data['date'])
    data['date'].unit = 'UTC'
    data['pwv'].unit = 'mm'

    # Refine results to only include datetimes indicated by kwargs
    return _search_dt_table(data, year=year, month=month, day=day, hour=hour)


def _check_transmission_args(date, airmass, model):
    """Check arguments for the function `transmission`

    This function provides argument checks for the `transmission` function. It
    checks argument types, if a datetime falls within the range of the locally
    available SuomiNet data, and if SuomiNet data is available near that
    datetime.

    Args:
        date    (datetime.datetime): A datetime value
        airmass             (float): An airmass value
        model (astropy.table.Table): A model for the PWV level at KPNO

    Returns:
        None
    """

    # Check argument types
    if not isinstance(date, datetime):
        raise TypeError("Argument 'date' (pos 1) must be a datetime instance")

    if date.tzinfo is None:
        msg = "Argument 'date' (pos 1) has no timezone information."
        raise ValueError(msg)

    if not isinstance(airmass, (float, int)):
        raise TypeError("Argument 'airmass' (pos 2) must be an int or float")

    # Check date falls within the range of available PWV data
    timestamp = _timestamp(date)
    w_data_less_than = np.where(model['date'] < timestamp)[0]
    if len(w_data_less_than) < 1:
        min_date = datetime.utcfromtimestamp(min(model['date']))
        msg = 'No local SuomiNet data found for datetimes before {0}'
        raise ValueError(msg.format(min_date))

    w_data_greater_than = np.where(timestamp < model['date'])[0]
    if len(w_data_greater_than) < 1:
        max_date = datetime.utcfromtimestamp(max(model['date']))
        msg = 'No local SuomiNet data found for datetimes after {0}'
        raise ValueError(msg.format(max_date))

    # Check for SuomiNet data available near the given date
    diff = model['date'] - timestamp
    interval = min(diff[diff > 0]) - max(diff[diff < 0])
    three_days_in_seconds = 24 * 60 * 60

    if three_days_in_seconds < interval:
        msg = ('Specified datetime falls within interval of missing SuomiNet' +
               ' data larger than 3 days ({0} interval found).')
        raise ValueError(msg.format(timedelta(seconds=interval)))


def transmission(date, airmass):
    """Return a model for the atmospheric transmission function due to PWV

    For a given datetime and airmass, return a model for the atmospheric
    transmission function due to precipitable water vapor (PWV) at Kitt Peak.
    The modeled transmission is returned as an astropy table with the columns
    'wavelength' and 'transmission'. Wavelength values range from 7000 to
    10,000 angstroms.

    Args:
        date (datetime.datetime): The datetime of the desired model
        airmass          (float): The airmass of the desired model

    Returns:
        trans_func (astropy.table.Table): The modeled transmission function
    """

    # Check for valid arguments
    pwv_model = Table.read(os.path.join(PWV_TAB_DIR, 'modeled_pwv.csv'))
    _check_transmission_args(date, airmass, pwv_model)

    # Determine the PWV level along line of sight as pwv(zenith) * airmass
    timestamp = _timestamp(date)
    pwv = np.interp(timestamp, pwv_model['date'], pwv_model['pwv']) * airmass

    # Read the first file to get an table of the considered wavelengths
    atm_model_files = glob.glob(os.path.join(ATM_MOD_DIR, '*.csv'))
    wavelength = Table.read(atm_model_files[0])['wavelength']

    # Read the astmospheric models into a 3D array
    pwv_values = []
    array_shape = (len(atm_model_files), len(wavelength))
    transmission_models = np.zeros(array_shape, dtype=np.float)
    for i, model_file in enumerate(atm_model_files):
        model_pwv = float(os.path.basename(model_file).split("_")[3])
        pwv_values.append(model_pwv)

        this_pwv_model = Table.read(model_file)
        transmission_models[i, :] = this_pwv_model['transmission']

    # Interpolate to find the transmission function
    interp_trans = interpn(points=(pwv_values, wavelength),
                           values=transmission_models,
                           xi=np.array([[pwv, x] for x in wavelength]))

    # Create a table to store the modeled transmission function
    trans_func = Table([wavelength, interp_trans],
                       names=['wavelength', 'transmission'],
                       dtype=[float, float])

    trans_func['wavelength'].unit = 'angstrom'
    trans_func['transmission'].unit = 'percent'
    return trans_func
