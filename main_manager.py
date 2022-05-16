import os
import json
import time
import logging
import tornado.httpclient
from tornado.web import Application, RequestHandler
from tornado.ioloop import IOLoop

##############################################################################
##############################################################################
##############################################################################

GENERAL_LOG_NAME = 'LOGGER_NAME'
GENERAL_LOG_LEVEL = 'LOG_LEVEL'
LM_CONFIG_URL = 'LOCAL_MANAGER_CONFIG_URL'
API_PORT = 'API_PORT'

OSENV_GENERAL_LOG_NAME = os.environ[GENERAL_LOG_NAME]
OSENV_GENERAL_LOG_LEVEL = os.environ[GENERAL_LOG_LEVEL]
OSENV_LM_CONFIG_URL = os.environ[LM_CONFIG_URL]
OSENV_API_PORT = os.environ[API_PORT]

TIME_LOG_NAME = ' Timing MAIN Manager '

##############################################################################
# Logging ####################################################################
##############################################################################

formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')


def logger_setup(name, level=OSENV_GENERAL_LOG_LEVEL):
    """Setup different loggers here"""

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(sh)
    logger.propagate = False

    return logger


def logger_file_setup(name, file_name, level=OSENV_GENERAL_LOG_LEVEL):
    """Setup different file-loggers here"""

    file_handler = logging.FileHandler(file_name)
    file_handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(file_handler)

    return logger


general_log = logger_setup(OSENV_GENERAL_LOG_NAME)
time_log = logger_setup(TIME_LOG_NAME)


##############################################################################
# TENTATIVE DICTS from MM Config #############################################
##############################################################################


"""
    sm_dict: Support Message dict

    sm_dict = {
        <msg_id> : <msg_endpoints>
        ...
    }
"""
sm_dict = {}
"""
    qtcode_dict: Quadtree code dict

    qtcode_dict = {
        <qtcode> : <msg_id>
        ...
    }
"""
qtcode_dict = {}

test_config = {}


def config_startup(cfg):
    """ Main Manager startup config handling"""
    body = cfg

    sm_dict = {}
    qtcode_dict = {}

    if body != {}:
        for key, value in body["lms"].items():
            for lc in value["local_config"]:
                for qt in lc["qtcode_list"]:
                    qtcode_dict.update(
                        {qt: lc["message"].get("id")})
                    sm_dict.update(
                        {lc["message"].get("id"):
                            lc["message"].get("endpoints")})
        return sm_dict, qtcode_dict
    else:
        return sm_dict, qtcode_dict


def show_current_configuration():
    general_log.info("Support Messages")
    general_log.info(json.dumps(sm_dict, sort_keys=True, indent=4))
    general_log.info("QT Codes")
    general_log.info(json.dumps(qtcode_dict, sort_keys=True, indent=4))

##############################################################################
# API Server #################################################################
##############################################################################


class Car_ApiServer(RequestHandler):
    """ API SERVER for handling calls from the cars """

    def get(self, id):
        """ GET calls handler
        Returns the Support Message assciated with car position, passed as
        quadtree code in the request URL

        /api/item/from_car_api/qtcode/<qtcode value>
        """
        received_post = time.time()
        sm_dict, qtcode_dict = config_startup(test_config)
        car_position = self.request.uri.replace(
            "/api/item/from_car_api/qtcode/", "")
        if car_position in qtcode_dict.keys() and test_config != {}:
            # for sm in sm_dict[qtcode_dict.get((car_position))]:
            #     self.set_status(200)
            #     self.set_header("Content-Type", 'application/json')
            #     self.write(sm)
            #     general_log.debug("SM %s" % str(sm))
            #     sent_reply = time.time()
            #     general_log.debug("Process time: %sms" %
            #                       str((sent_reply-received_post)*1000))
            sm = json.dumps(sm_dict[qtcode_dict.get((car_position))])
            self.set_status(200)
            self.set_header("Content-Type", 'application/json')
            self.write(sm)
            general_log.debug("SM %s" % str(sm))
            sent_reply = time.time()
            general_log.debug("Process time: %sms" %
                              str((sent_reply-received_post)*1000))
        else:
            self.set_status(404)
            self.set_header("Content-Type", 'application/json')
            self.write({"warning": "Quadtreee code NOT within my scope"})


class LM_ApiServer(RequestHandler):
    """ clear
    API SERVER to update the main manager and local manager configs """

    async def post(self, id):
        """Handles the behaviour of POST calls"""
        # self.write({"info": "NEW configuration RECEIVED"})
        global test_config
        global sm_dict
        global qtcode_dict
        test_config = json.loads(self.request.body)
        await post_local_mgr_config(test_config)
        sm_dict, qtcode_dict = config_startup(test_config)

        show_current_configuration()

        self.write({"info": "NEW configuration RECEIVED and APPLIED"})


def make_app():
    urls = [
        (r"/api/item/configure_me/([^/]+)?", LM_ApiServer),
        (r"/api/item/from_car_api/qtcode/([^/]+)?", Car_ApiServer)
    ]
    return Application(urls, debug=True)


##############################################################################
# API CLients ################################################################
##############################################################################

async def post_local_mgr_config(cfg):
    """ Method to send the local manager its configs """
    http_client = tornado.httpclient.AsyncHTTPClient()

    for lm, config in cfg["lms"].items():
        url = "http://" + config["ep"] + OSENV_LM_CONFIG_URL
        body = json.dumps(config)

        await inject_lm_configuration(lm, url, body, http_client)


async def inject_lm_configuration(lm, url, body, client=None):
    if client is None:
        client = tornado.httpclient.AsyncHTTPClient()

    while True:
        try:
            response = await client.fetch(
                url,
                method='POST',
                body=body)

            # general_log.info
            general_log.info("Sent LM '%s' config, response: %s" % (
                lm, str(response)))

        except Exception as e:
            general_log.debug("Error: %s" % e)
            time.sleep(5)
        else:
            break


##############################################################################
# MAIN #######################################################################
##############################################################################


if __name__ == '__main__':

    app = make_app()
    app.listen(OSENV_API_PORT)
    general_log.info("Started Main Manager REST Server")
    IOLoop.instance().start()
