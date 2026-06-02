from flask import Flask, request, jsonify
import swisseph as swe
import math
from datetime import datetime, timezone
import requests

app = Flask(__name__)

swe.set_ephe_path('/usr/share/ephe')

PLANETS = {
    'soleil': swe.SUN,
    'lune': swe.MOON,
    'mercure': swe.MERCURY,
    'venus': swe.VENUS,
    'mars': swe.MARS,
    'jupiter': swe.JUPITER,
    'saturne': swe.SATURN,
    'uranus': swe.URANUS,
    'neptune': swe.NEPTUNE,
    'pluton': swe.PLUTO,
}

SIGNS = ['Bélier','Taureau','Gémeaux','Cancer','Lion','Vierge',
         'Balance','Scorpion','Sagittaire','Capricorne','Verseau','Poissons']

HOUSES_NAMES = ['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII']

def deg_to_sign(deg):
    deg = deg % 360
    sign_index = int(deg / 30)
    deg_in_sign = deg % 30
    return SIGNS[sign_index], round(deg_in_sign, 4)

def calc_julday(year, month, day, hour_decimal):
    return swe.julday(year, month, day, hour_decimal)

def calc_planets(jd):
    result = {}
    for name, pid in PLANETS.items():
        pos, _ = swe.calc_ut(jd, pid)
        sign, deg = deg_to_sign(pos[0])
        result[name] = {
            'longitude': round(pos[0], 4),
            'signe': sign,
            'degre': deg,
            'retrograde': pos[3] < 0
        }
    # Lilith (Lune Noire Moyenne)
    pos, _ = swe.calc_ut(jd, swe.MEAN_APOG)
    sign, deg = deg_to_sign(pos[0])
    result['lilith'] = {
        'longitude': round(pos[0], 4),
        'signe': sign,
        'degre': deg,
        'retrograde': False
    }
    # Nœud Nord
    pos, _ = swe.calc_ut(jd, swe.MEAN_NODE)
    sign, deg = deg_to_sign(pos[0])
    result['noeud_nord'] = {
        'longitude': round(pos[0], 4),
        'signe': sign,
        'degre': deg,
        'retrograde': True
    }
    return result

def calc_houses(jd, lat, lon):
    cusps, ascmc = swe.houses(jd, lat, lon, b'P')  # Placidus
    houses = {}
    for i, cusp in enumerate(cusps):
        sign, deg = deg_to_sign(cusp)
        houses[HOUSES_NAMES[i]] = {
            'longitude': round(cusp, 4),
            'signe': sign,
            'degre': deg
        }
    asc_sign, asc_deg = deg_to_sign(ascmc[0])
    mc_sign, mc_deg = deg_to_sign(ascmc[1])
    return houses, {
        'longitude': round(ascmc[0], 4), 'signe': asc_sign, 'degre': asc_deg
    }, {
        'longitude': round(ascmc[1], 4), 'signe': mc_sign, 'degre': mc_deg
    }

def calc_part_fortune(asc, sun, moon):
    fortune = (asc + moon - sun) % 360
    sign, deg = deg_to_sign(fortune)
    return {'longitude': round(fortune, 4), 'signe': sign, 'degre': deg}

def get_planet_house(planet_lon, cusps_list):
    for i in range(12):
        start = cusps_list[i] % 360
        end = cusps_list[(i + 1) % 12] % 360
        lon = planet_lon % 360
        if start <= end:
            if start <= lon < end:
                return HOUSES_NAMES[i]
        else:
            if lon >= start or lon < end:
                return HOUSES_NAMES[i]
    return HOUSES_NAMES[0]

ASPECT_ORBS = {
    'conjonction': (0, 8),
    'sextile': (60, 6),
    'carre': (90, 8),
    'trigone': (120, 8),
    'opposition': (180, 8),
    'quinconce': (150, 3),
    'semi_sextile': (30, 2),
}

def calc_aspects(planets):
    aspects = []
    planet_list = list(planets.items())
    for i in range(len(planet_list)):
        for j in range(i + 1, len(planet_list)):
            name1, p1 = planet_list[i]
            name2, p2 = planet_list[j]
            diff = abs(p1['longitude'] - p2['longitude']) % 360
            if diff > 180:
                diff = 360 - diff
            for asp_name, (asp_angle, orb) in ASPECT_ORBS.items():
                if abs(diff - asp_angle) <= orb:
                    aspects.append({
                        'planete1': name1,
                        'planete2': name2,
                        'aspect': asp_name,
                        'angle': round(diff, 2),
                        'orbe': round(abs(diff - asp_angle), 2)
                    })
                    break
    return aspects

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'andrei-care-astro'})

@app.route('/theme', methods=['POST'])
def theme():
    data = request.get_json()
    try:
        year = int(data['year'])
        month = int(data['month'])
        day = int(data['day'])
        hour = float(data['hour'])      # heure décimale UTC
        lat = float(data['lat'])
        lon = float(data['lon'])
    except (KeyError, ValueError, TypeError) as e:
        return jsonify({'error': f'Paramètres manquants ou invalides: {str(e)}'}), 400

    jd = calc_julday(year, month, day, hour)
    planets = calc_planets(jd)
    cusps, asc, mc = calc_houses(jd, lat, lon)
    fortune = calc_part_fortune(asc['longitude'], planets['soleil']['longitude'], planets['lune']['longitude'])
    aspects = calc_aspects(planets)

    # Maison de chaque planète
    cusps_list = [cusps[h]['longitude'] for h in HOUSES_NAMES]
    for name in planets:
        planets[name]['maison'] = get_planet_house(planets[name]['longitude'], cusps_list)

    return jsonify({
        'julday': jd,
        'planetes': planets,
        'maisons': cusps,
        'ascendant': asc,
        'mc': mc,
        'part_fortune': fortune,
        'aspects': aspects
    })

if __name__ == '__main__':
    app.run(debug=False)
