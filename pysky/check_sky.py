"""This module is used to see if an object is visible."""
from .const import Const
from .logger import Logger
import numpy as np
from astroplan import Observer
from astropy.coordinates import EarthLocation
from astropy.time import Time
import astropy.units as u


def is_object_visible(
        celestial_obj,
        secz_max=3.0
) -> tuple:
    """
    :param celestial_obj: object to view (astropy.coordinates.SkyCoord())
    :param start_time:  starting range for the
                        viewing time (astropy.time.Time())
    :param end_time: ending range for the viewing time (astropy.time.Time())
    :param secz_max:
    :param location: location of viewing site
                     (astropy.coordinates.EarthLocation())
    :return: tuple if the object is up or not during
             the time range given (string, alt, az || '', '', '')
    """
    location = Observer(
        location=EarthLocation.from_geodetic(
            Const.LATITUDE * u.deg,
            Const.LONGITUDE * u.deg,
            Const.ELEVATION * u.m
        ),
        name='location',
        timezone="US/Central"
    )
    start_time = Time(
        f'{Const.START_YEAR}-' +
        f'{Const.START_MONTH}-' +
        f'{Const.START_DAY} ' +
        f'{Const.START_TIME}',
        format='iso'
    )
    end_time = Time(
        f'{Const.END_YEAR}-' +
        f'{Const.END_MONTH}-' +
        f'{Const.END_DAY} ' +
        f'{Const.END_TIME}',
        format='iso'
    )
    Logger.log(f"Checking sec(z) for {celestial_obj.name}.")
    start_secz = location.altaz(start_time, celestial_obj).secz
    end_secz = location.altaz(end_time, celestial_obj).secz
    start_altaz = location.altaz(start_time, celestial_obj)

    try:
        if start_secz < secz_max or end_secz < secz_max:
            Logger.log(f"Found sec(z) for {celestial_obj.name}.")
            Logger.log(
                f"Zenith={start_altaz.zen} " +
                f"Altitiude={start_altaz.alt}" +
                f"Azimuth={start_altaz.az}"
            )
            return start_altaz.zen, start_altaz.alt, start_altaz.az
    except ValueError as e:
        Logger.log(
            f"Could not find sec(z) for {celestial_obj.name}.",
            40
        )
        Logger.log(str(e), 40)
        Logger.log(start_secz, 40)
        return '', '', ''
    return '', '', ''
