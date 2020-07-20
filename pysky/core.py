"""Main module that calls all relevant modules."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import astroplan
import astropy
import astropy.units as u
import numpy
from astroplan import (FixedTarget, OldEarthOrientationDataWarning,
                       download_IERS_A)
from astropy.coordinates import Angle, SkyCoord
from tqdm import tqdm

from .argument_parser import cli_parse
from .astro_info import get_ephemeries_info
from .catalog_parse import parse_caldwell, parse_messier
from .check_sky import is_object_visible
from .const import Const
from .image_manipulation import overlay_text
from .jpl_horizons_query import ephemeries_query
from .logger import Logger
from .moonquery import query
from .output import to_html_list, to_html_table
from .prefs import check_integrity, read_user_prefs
from .simbad import get_brightness, get_constellation, get_distance, get_ra_dec
from .skyview import get_skyview_img

download_IERS_A()


def invoke():
    """
    Call all other relevant functions.
    """
    download_IERS_A()

    cli_parse()

    check_integrity()

    CALDWELL_OBJECTS = parse_caldwell(Const.ROOT_DIR)
    MESSIER_OBJECTS = parse_messier(Const.ROOT_DIR)
    USER_OBJECTS = read_user_prefs()

    gen_moon_data()

    STARS, EPHEMERIES = query_jpl_horizons(USER_OBJECTS)

    EPHEMERIES_BODIES = list(EPHEMERIES.keys())

    # api and returns the the list of stars
    invoke_skyview(STARS)
    # Open cache file
    cache_file = json.loads(open(f"{Const.ROOT_DIR}/data/cache", "r").read())
    for star in STARS:
        cache_file = set_simbad_values(star, cache_file)
    temp_cache = {**cache_file, **EPHEMERIES}
    # Dump cache file
    with open(f"{Const.ROOT_DIR}/data/cache", "w") as json_out:
        json.dump(temp_cache, json_out, indent=4, sort_keys=True)
    cache_file = json.loads(open(f"{Const.ROOT_DIR}/data/cache", "r").read())

    set_img_txt(STARS)
    # Iterate through the ephemeries to add information
    for body in tqdm(EPHEMERIES_BODIES):
        cache_file = get_ephemeries_info(body, cache_file)

    # Dump cache file
    with open(f"{Const.ROOT_DIR}/data/cache", "w") as json_out:
        json.dump(cache_file, json_out, indent=4, sort_keys=True)

    visible_objs = dict()
    visible = dict()
    for star in cache_file:
        Logger.log("Gathering zen, altitude, and " + f"azimuth for {star}...")
        try:
            start_altitude, start_azimuth, end_altitude, end_azimuth = get_visible(
                star,
                cache_file[star]["Coordinates"]["ra"],
                cache_file[star]["Coordinates"]["dec"],
            )
        except KeyError:
            continue
        if len(set([start_altitude, start_azimuth, end_altitude, end_azimuth])) != 1:
            Logger.log(f"Sucessfully gathered data for {star}!\n")
            visible = {str(star): dict()}
            if start_altitude != "-":
                visible[star]["Start Alt."] = round(
                    float(start_altitude.to_string(decimal=True))
                )
            else:
                visible[star]["Start Alt."] = "-"
            if start_azimuth != "-":
                visible[star]["Start Az."] = round(
                    float(start_azimuth.to_string(decimal=True))
                )
            else:
                visible[star]["Start Az."] = "-"
            if end_altitude != "-":
                visible[star]["End Alt."] = round(
                    float(end_altitude.to_string(decimal=True))
                )
            else:
                visible[star]["End Alt."] = "-"
            if end_azimuth != "-":
                visible[star]["End Az."] = round(
                    float(end_azimuth.to_string(decimal=True))
                )
            else:
                visible[star]["End Az."] = "-"
            visible_objs.update(visible)

    # Dump cache file
    with open(f"{Const.ROOT_DIR}/data/cache", "w") as json_out:
        json.dump(cache_file, json_out, indent=4, sort_keys=True)
    cache_file = json.loads(open(f"{Const.ROOT_DIR}/data/cache", "r").read())

    # Iterate through the ephemeries to add information
    for body in tqdm(EPHEMERIES_BODIES):
        cache_file = get_ephemeries_info(body, cache_file)

    # Dump cache file
    with open(f"{Const.ROOT_DIR}/data/cache", "w") as json_out:
        json.dump(cache_file, json_out, indent=4, sort_keys=True)

    visible_messier = dict()
    visible = dict()
    for m_obj in MESSIER_OBJECTS.keys():
        if (
            not isinstance(MESSIER_OBJECTS[str(m_obj)]["Brightness"], str)
            and MESSIER_OBJECTS[str(m_obj)]["Brightness"] <= Const.MIN_V
        ):
            Logger.log("Gathering zen, altitude, and " + f"azimuth for {m_obj}...")
            start_altitude, start_azimuth, end_altitude, end_azimuth = get_visible(
                m_obj,
                MESSIER_OBJECTS[m_obj]["Coordinates"]["ra"],
                MESSIER_OBJECTS[m_obj]["Coordinates"]["dec"],
            )
            if (
                len(set([start_altitude, start_azimuth, end_altitude, end_azimuth]))
                != 1
            ):
                Logger.log(f"Sucessfully gathered data for {m_obj}!\n")
                visible[str(m_obj)] = dict()
                visible[str(m_obj)]["Type"] = MESSIER_OBJECTS[m_obj]["Type"]
                try:
                    visible[str(m_obj)]["Start Alt. (°)"] = round(
                        float(start_altitude.to_string(decimal=True))
                    )
                except AttributeError:
                    visible[str(m_obj)]["Start Alt. (°)"] = start_altitude
                try:
                    visible[str(m_obj)]["Start Az. (°)"] = round(
                        float(start_azimuth.to_string(decimal=True))
                    )
                except AttributeError:
                    visible[str(m_obj)]["Start Az. (°)"] = start_azimuth
                try:
                    visible[str(m_obj)]["End Alt. (°)"] = round(
                        float(end_altitude.to_string(decimal=True))
                    )
                except AttributeError:
                    visible[str(m_obj)]["End Alt. (°)"] = end_altitude
                try:
                    visible[str(m_obj)]["End Az. (°)"] = round(
                        float(end_azimuth.to_string(decimal=True))
                    )
                except AttributeError:
                    visible[str(m_obj)]["End Az. (°)"] = end_azimuth
                visible[str(m_obj)]["Constellation"] = MESSIER_OBJECTS[m_obj][
                    "Constellation"
                ]
                visible[str(m_obj)]["Brigntness"] = MESSIER_OBJECTS[m_obj]["Brightness"]
                visible[str(m_obj)]["Distance (Pm)"] = int(
                    (float("%.2g" % MESSIER_OBJECTS[m_obj]["Distance"]))
                )
                visible_messier.update(visible)
            else:
                Logger.log(f"{m_obj} is not visible.", 30)
        else:
            Logger.log(
                f"Ignoring {m_obj} since it is below the magnitude threshold of {Const.MIN_V}",
                30,
            )
    visible_caldwell = dict()
    visible = dict()
    for c_obj in CALDWELL_OBJECTS.keys():
        if (
            not isinstance(CALDWELL_OBJECTS[str(c_obj)]["Brightness"], str)
            and CALDWELL_OBJECTS[str(c_obj)]["Brightness"] <= Const.MIN_V
        ):
            Logger.log("Gathering zen, altitude, and " + f"azimuth for {c_obj}...")
            start_altitude, start_azimuth, end_altitude, end_azimuth = get_visible(
                c_obj,
                CALDWELL_OBJECTS[c_obj]["Coordinates"]["ra"],
                CALDWELL_OBJECTS[c_obj]["Coordinates"]["dec"],
            )
            if (
                len(set([start_altitude, start_azimuth, end_altitude, end_azimuth]))
                != 1
            ):
                Logger.log(f"Sucessfully gathered data for {c_obj}!\n")
                visible[str(c_obj)] = dict()
                visible[str(c_obj)]["Type"] = CALDWELL_OBJECTS[c_obj]["Type"]
                try:
                    visible[str(c_obj)]["Start Alt. (°)"] = round(
                        float(start_altitude.to_string(decimal=True))
                    )
                except AttributeError:
                    visible[str(c_obj)]["Start Alt. (°)"] = start_altitude
                try:
                    visible[str(c_obj)]["Start Az. (°)"] = round(
                        float(start_azimuth.to_string(decimal=True))
                    )
                except AttributeError:
                    visible[str(c_obj)]["Start Az. (°)"] = start_azimuth
                try:
                    visible[str(c_obj)]["End Alt. (°)"] = round(
                        float(end_altitude.to_string(decimal=True))
                    )
                except AttributeError:
                    visible[str(c_obj)]["End Alt. (°)"] = end_altitude
                try:
                    visible[str(c_obj)]["End Az. (°)"] = round(
                        float(end_azimuth.to_string(decimal=True))
                    )
                except AttributeError:
                    visible[str(c_obj)]["End Az. (°)"] = end_azimuth
                visible[str(c_obj)]["Constellation"] = CALDWELL_OBJECTS[c_obj][
                    "Constellation"
                ]
                visible[str(c_obj)]["Brigntness"] = CALDWELL_OBJECTS[c_obj][
                    "Brightness"
                ]
                visible[str(c_obj)]["Distance (Pm)"] = int(
                    float("%.2g" % CALDWELL_OBJECTS[c_obj]["Distance"])
                )
                visible_caldwell.update(visible)
            else:
                Logger.log(f"{c_obj} is not visible.", 30)
        else:
            Logger.log(
                f"Ignoring {c_obj} since it is below the magnitude threshold of {Const.MIN_V}",
                30,
            )

    # set_img_txt(visible_messier)
    # set_img_txt(visible_caldwell)

    s_list = list()
    v_obj = dict()
    for star, data in cache_file.items():
        v_obj[star] = {}
        try:
            v_obj[star]["Type"] = cache_file[star]["Type"].title()
        except KeyError:
            v_obj[star]["Type"] = "-"
        try:
            v_obj[star]["Start Alt. (°)"] = visible_objs[star]["Start Alt."]
        except KeyError:
            v_obj[star]["Alt. (°)"] = "-"
        try:
            v_obj[star]["Start Az. (°)"] = visible_objs[star]["Start Az."]
        except KeyError:
            v_obj[star]["Start Az. (°)"] = "-"
        try:
            v_obj[star]["End Alt. (°)"] = visible_objs[star]["End Alt."]
        except KeyError:
            v_obj[star]["End. (°)"] = "-"
        try:
            v_obj[star]["End Az. (°)"] = visible_objs[star]["End Az."]
        except KeyError:
            v_obj[star]["End Az. (°)"] = "-"
        try:
            v_obj[star]["Constellation"] = cache_file[star]["Constellation"]
        except KeyError:
            v_obj[star]["Constellation"] = "-"
        try:
            v_obj[star]["Brightness"] = cache_file[star]["Brightness"]
        except KeyError:
            v_obj[star]["Brightness"] = "-"
        try:
            v_obj[star]["Distance (Pm)"] = int(
                float("%.2g" % cache_file[star]["Distance"])
            )
        except KeyError:
            v_obj[star]["Distance (Pm)"] = "-"

    for key, value in v_obj.items():
        s_list.append({str(key).title(): value})

    m_list = list()
    for key, value in visible_messier.items():
        m_list.append({key: value})

    c_list = list()
    for key, value in visible_caldwell.items():
        c_list.append({key: value})

    write_out(s_list, code=0, filename="Stars")
    write_out(m_list, code=0, filename="VisibleMessier")
    write_out(c_list, code=0, filename="VisibleCaldwell")

    cel_objs = s_list + m_list + c_list
    write_out(cel_objs, code=1)


def set_simbad_values(celestial_obj: str, cache_file: dict) -> dict:
    """
    Call the simbad module and get the star's properties.

    :param celestial_obj: Object to get values for.
    :param cache_file: Opened cache file to apply changes to.
    :return: Cache file with added simbad values.
    """
    cache_file[celestial_obj]["Brightness"] = get_brightness(celestial_obj)

    cache_file[celestial_obj]["Constellation"] = get_constellation(celestial_obj)

    ra_dec = get_ra_dec(celestial_obj)
    cache_file[celestial_obj]["Coordinates"] = {"ra": ra_dec[0], "dec": ra_dec[1]}
    distance = get_distance(celestial_obj)
    cache_file[celestial_obj]["Distance"] = distance
    return cache_file


def query_jpl_horizons(ephemeries_objs: list) -> tuple:
    """
    Run ephemeries_query in as many threads as specified.

    :param ephemeries_objs: List of objects to retrieve data for.
    """
    with ThreadPoolExecutor(max_workers=Const.THREADS) as executor:
        results = executor.map(ephemeries_query, ephemeries_objs)

    unknown_objs = list()
    known_objs = list()
    for result in results:
        ephemeris, celestial_obj = result
        if ephemeris is not None:
            known_objs.append(ephemeris)
        else:
            unknown_objs.append(celestial_obj)
    ephemerides = dict()
    for obj in known_objs:
        ephemerides.update(obj)
    return (unknown_objs, ephemerides)


def invoke_skyview(stars: list) -> None:
    """
    Run skyview in as many threads as specified.

    :param stars: List of string of the stars download witrh skyview.
    """
    with ThreadPoolExecutor(max_workers=Const.THREADS) as executor:
        executor.map(get_skyview_img, stars)


def set_img_txt(celestial_objs: list) -> None:
    """
    Set the text on the image of the object.

    :param celestial_objs: List of strings of the objects to overlay text on.
    """
    with ThreadPoolExecutor(max_workers=Const.THREADS) as executor:
        executor.map(overlay_text, celestial_objs)


def get_visible(object_name: str, ra, dec) -> tuple:
    """
    Check to see if the given object is
    visible at a location in a certain time.
    :param start_time: Astropy.time object starting time range.
    :param end_time: Astropy.time object ending time range.
    :param location: Astroplan.observer object as your location.
    :param celestial_objs: List of objects to check.
    :return: Tuple of visible objects.
    """

    try:
        if isinstance(ra, list) and isinstance(dec, list):
            ra = ((ra[0] / 24) + (ra[1] / 60) + (ra[2] / 3600)) * 360
            dec = dec[0] + (dec[1] / 60) + (dec[2] / 3600)
        elif isinstance(ra, numpy.float64) and isinstance(dec, numpy.float64):
            pass
        celestial_obj_coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg)
        # celestial_obj = FixedTarget.from_name(object_name)
        celestial_obj = FixedTarget(coord=celestial_obj_coord, name=object_name)
        start_altitude, start_azimuth, end_altitude, end_azimuth = is_object_visible(
            celestial_obj=celestial_obj, secz_max=Const.SECZ_MAX
        )
        return (start_altitude, start_azimuth, end_altitude, end_azimuth)
    except astropy.coordinates.name_resolve.NameResolveError as e:
        Logger.log(
            "Unable to gather name, start_altaz.alt, and "
            + f"start_altaz.az for {object_name}!\n",
            40,
        )
        Logger.log(str(e), 40)
        return "-", "-", "-", "-"
    except TypeError as e:
        Logger.log(
            "Unable to gather name, start_altaz.alt, and "
            + f"start_altaz.az for {object_name}!\n",
            40,
        )
        Logger.log(str(e), 40)
        return "-", "-", "-", "-"


def gen_moon_data():
    Logger.log("Retreiving data for tonight's moon...")
    illumination, phase = query()
    Logger.log("Data for tonight's moon:")
    Logger.log(f"Illumination: {illumination}\tPhase: {phase}")
    Logger.log(f"Writing data to `{Const.SLIDESHOW_DIR}/PySkySlideshow/`...")
    write_out(
        celestial_objs=[
            {
                "Moon": {
                    "Date": f"{Const.START_YEAR}-{Const.START_MONTH}-{Const.START_DAY}",
                    "Illumination": illumination,
                    "Phase": phase,
                }
            }
        ],
        filename=f"moon_{Const.START_YEAR}-{Const.START_MONTH}-{Const.START_DAY}",
    )
    Logger.log("Wrote file!")


def write_out(celestial_objs: list, code=0, filename=None):
    if code == 0:
        Logger.log("Writing objects to HTML list")
        to_html_list(celestial_objs, filename=filename)
        Logger.log("Wrote HTML list")
    if code == 1:
        Logger.log("Writing objects to HTML table")
        to_html_table(celestial_objs)
        Logger.log("Wrote HTML table.")
