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
from astropy.table import Table

from create_pwv_models import _update_suomi_data
from create_pwv_models import _update_pwv_model

__author__ = 'Daniel Perrefort'
__copyright__ = 'Copyright 2017, Daniel Perrefort'
__credits__ = 'Alexander Afanasyev'

__license__ = 'GPL V3'
__email__ = 'djperrefort@gmail.com'
__status__ = 'Development'


# Define necessary directory paths
ATM_MOD_DIR = './atm_models'  # Location of atmospheric models
PWV_TAB_DIR = './pwv_tables/'  # Where to write PWV data tables


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

    with open('../CONFIG.txt', 'rb') as ofile:
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


def _raise_arg_types(year, month, day, hour):
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

    # Check the year argument
    if not (isinstance(year, int) or year is None):
        raise TypeError("Argument 'year' (pos 1) must be an integer")

    elif isinstance(year, int) and year < 2010:
        raise ValueError('pwv_kpno does not provide data years prior to 2010')

    elif isinstance(year, int) and year > datetime.now().year:
        raise ValueError("Argument 'year' (pos 1) is larger than current year")

    # Check the month argument
    if not (isinstance(month, int) or month is None):
        raise TypeError("Argument 'month' (pos 2) must be an integer")

    elif isinstance(month, int) and (month < 0 or month > 12):
        raise ValueError('Invalid value for month: ' + str(month))

    # Check the day argument
    if not (isinstance(day, int) or day is None):
        raise TypeError("Argument 'day' (pos 3) must be an integer")

    elif isinstance(day, int) and (day < 0 or day > 31):
        raise ValueError('Invalid value for day: ' + str(day))

    # Check the hour argument
    if not (isinstance(hour, int) or hour is None):
        raise TypeError("Argument 'hour' (pos 4) must be an integer")

    elif isinstance(hour, int) and (hour < 0 or hour > 24):
        raise ValueError('Invalid value for hour: ' + str(hour))


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

    # Check for valid arg types
    _raise_arg_types(year, month, day, hour)

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
    _raise_arg_types(year, month, day, hour)

    # Read in SuomiNet measurements from the master table
    data = Table.read(os.path.join(PWV_TAB_DIR, 'modeled_pwv.csv'))

    # Convert UNIX timestamps to UTC
    data['date'] = np.vectorize(datetime.utcfromtimestamp)(data['date'])
    data['date'].unit = 'UTC'
    data['pwv'].unit = 'mm'

    # Refine results to only include datetimes indicated by kwargs
    return _search_dt_table(data, year=year, month=month, day=day, hour=hour)


def transmission(date, airmass):
    """Return a model for the atmospheric transmission function due to PWV

    For a given UTC datetime and airmass, return a model for the atmospheric
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

    # Check for valid arg types
    if not isinstance(date, datetime):
        raise TypeError("Argument 'date' (pos 1) must be a datetime instance")

    if not isinstance(airmass, (float, int)):
        raise TypeError("Argument 'airmass' (pos 2) must be an int or float")

    # Check the specified datetime falls within the range of available PWV data
    pwv_model = Table.read(os.path.join(PWV_TAB_DIR, 'modeled_pwv.csv'))
    timestamp = (date - datetime(1970, 1, 1)).total_seconds()
    if timestamp < 1277424900:
        msg = 'Cannot model transmission prior to 2010-06-25 00:15:00'
        raise ValueError(msg)

    if max(pwv_model['date']) < timestamp:
        max_date = datetime.utcfromtimestamp(max(pwv_model['date']))
        msg = 'No local SuomiNet data found for datetimes after {0}'
        raise ValueError(msg.format(max_date))

    # Check that there is SuomiNet data available near the specified date
    diff = pwv_model['date'] - timestamp
    interval = min(diff[diff > 0]) - max(diff[diff < 0])
    if 259200 < interval:
        msg = ('Specified datetime falls within interval of missing SuomiNet' +
               ' data larger than 3 days ({0} interval found).')
        raise ValueError(msg.format(timedelta(seconds=interval)))

    # Determine the PWV level along line of sight as pwv @ zenith * airmass
    pwv = np.interp(timestamp, pwv_model['date'], pwv_model['pwv']) * airmass

    # Read atmospheric models from file {pwv value (int), data table (astropy)}
    models = {float(os.path.basename(path).split("_")[3]): Table.read(path)
              for path in glob.glob(os.path.join(ATM_MOD_DIR, '*.csv'))}

    # Create a table to store the transmission function
    wavelengths = models[min(models.keys())]['wavelength']
    trans_func = Table(names=['wavelength', 'transmission'])

    # Calculate the transmission function
    for i, wvlngth in enumerate(wavelengths):
        # Get a list of the modeled transmission for each pwv level
        trans = [models[pwv]['transmission'][i] for pwv in models]

        # Interpolate to find the transmission
        interp_trans = np.interp(pwv, list(models.keys()), trans)
        trans_func.add_row([wvlngth, interp_trans])

    return trans_func
