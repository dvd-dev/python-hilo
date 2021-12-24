[![Total alerts](https://img.shields.io/lgtm/alerts/g/dvd-dev/python-hilo.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/dvd-dev/python-hilo/alerts/)
[![Language grade: Python](https://img.shields.io/lgtm/grade/python/g/dvd-dev/python-hilo.svg?logo=lgtm&logoWidth=18)](https://lgtm.com/projects/g/dvd-dev/python-hilo/context:python)

# python-hilo

`python-hilo` (aka `pyhilo`) is a Python 3.9, `asyncio`-driven interface to the unofficial
Hilo API from Hydro Quebec. This is meant to be integrated into Home Assistant.

Nothing is fully functional right now except for the PoC. Before this package, the Hilo API
was returning all information via some REST calls. Since the end of 2021, Hilo has deprecated
some of the endpoints including the ones that returns the status of the devices. This was
replaced with a websocket system using Google Firebase.

## Running the PoC

```
$ python -m virtualenv .venv
$ source .venv/bin/activate
$ pip install -r requirements.txt
$ cat << EOF > .env
export hilo_username="moi@gmail.com"
export hilo_password="secretpassword"
$ source .env
$ ./test.py
```

Home assistant integration is available [here](https://github.com/dvd-dev/hilo)

## TODO
- Type everything: almost done, got a few "type: ignore" to fix

## Later?
- Full docstrings and doc generation
- Unit testing
- Functional testing

If anyone wants to contribute, feel free to submit a PR. If you'd like to sync up first, you can
fire me an email me@dvd.dev
