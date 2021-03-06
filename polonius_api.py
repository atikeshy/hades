# this is the script to take the suspected and takedown cases and import into polonius
# It has a limit to stop a crazy amount of suspected cases being added by mistake, default is 20
# an unlimited number of takedown cases can be sent to polonius
##########################
# run the script with for example to set a limit of 40 suspected cases ..polonius_api.py -c 40
# polonius_api -h will display this help.
#
# Logging is turned on and is called hades.log


# TODO change API to send country manager and seller and product as seperate entities - RICH
# TODO seperate configuration into a different class to be proper and all that


# Import libraries
import requests
from sqlalchemy import create_engine
import pandas as pd
import logging
import argparse


# create the connection to the database
engine = create_engine("sqlite:///db/hades.db", echo=False)

# define globals development
caseUrl = "https://syngenta.poloniouslive.com/syngentatraining/public/oauth/task/v1/mapping/HadesUATProductCounterfeit"
infringUrl = "https://syngenta.poloniouslive.com/syngentatraining/public/oauth/task/v1/mapping/HadesUATProductInf"
tokenurl = "https://syngenta.poloniouslive.com/syngentatraining/pcmsrest/oauth/token?"
secret = "TbKs0R3e@A6V!p6c^Wq6CdPc"

# define globals production
# infringUrl ="https://syngenta.poloniouslive.com/syngenta/public/oauth/task/v1/mapping/HadesNoProductInf"
# tokenurl="https://syngenta.poloniouslive.com/syngenta/pcmsrest/oauth/token?"
# caseUrl ="https://syngenta.poloniouslive.com/syngenta/public/oauth/task/v1/mapping/HadesNoProduct"
# secret="D2s8tFJh79cxrQnUmyjNrZ69"

# get any optional arguments e.g polonius_api.py -c 20
parser = argparse.ArgumentParser(
    description="Number of cases to process and send to Polonius via API"
)
parser.add_argument(
    "-c", type=int, help="This sets the limit of cases to process", default=20
)
args = parser.parse_args()
limit = args.c


def set_logging(name, level):
    # set logging up
    logger = logging.getLogger(name)
    logger.setLevel(level)
    filelog = logging.FileHandler("hadesv2.log")
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
    )
    filelog.setFormatter(formatter)
    logger.addHandler(filelog)
    return logger


# get the authorisation token
def get_token(url, secret):
    # Creates header for OAuth request

    payload = {
        "client_secret": secret,
        "client_id": "publicRestCall",
        "grant_type": "client_credentials",
    }

    # request a token for access
    try:
        r = requests.post(url, data=payload)

    except:
        logger.error("can not reach polonius server and exchange certificates")
        return False

    token = str(r.json()["access_token"])
    # setup API associated headers
    return {"Authorization": "Bearer " + token, "Content-Type": "text/plain"}


# get product_details .. i.e standard prices and categories for any sub category e.g professional solutions is a sub cat of crop protection
# We have set the figures here
def get_product_details(business):

    switcher = {
        "Crop Protection": ["Crop Protection", "Crop", "35", "2"],
        "Seeds": ["Seeds", "Seed", "35", "2"],
        "Professional Solutions": [
            "Crop Protection",
            "Professional solutions",
            "150",
            "1",
        ],
    }

    # send False if no business unit found
    return switcher.get(business, [False, False, False, False])


# payload is the case data to send to polonius
def get_casePayload(row, businessUnit,category, price, quantity):
    
    #get rid of "null" comments in polonius  
    comments=lambda comment: " " if comment==None else comment

    return {
        "referenceNumber":"",
        "region": row["region"],
        "country": row["country"],
        "businessUnit": businessUnit,
        "offenceType": "Online Counterfeit",
        "justification": comments( row["comments"]),
        "notes": "HADES UPLOAD: " 
        + str(row["category"])
        + " \n\n date found : "
        + str(row["date_found"])
        + " \n\n Product Title: "
        + str(row["product"]),
        "sellerName": row["seller"],
        "sellerNotes": "seller found from Hades on " + str(row["date_found"]),
        "productName": row["product"],
        "category": category,
        "listingURL": row["url"],
        "dateFound": row["date_found"],
        "quantity": quantity,
        "price": price,
        "SecProfFirstname": row["SP_firstname"],
        "SecProfLastname": row["SP_lastname"],
    }


def get_cases(category, Notthisuser):
    categories = ",".join(category)
    sql = f"SELECT * FROM advert where category in ({categories}) and polonius_caseid is null and updated_by !={Notthisuser} "

    return pd.read_sql(sql, engine)


# send all ze data to polonius
def send_data(headers, Url, casePayload):
    try:
        r = requests.post(url=Url, headers=headers, json=casePayload)

    except:
        logger.error("There is a problem with connecting to the API")
        return False

    if r.json()["taskId"] == "0":

        logger.error("case was not added please check the payload %s ", casePayload)
        return False
    else:
        return r.json()


################Start of main program ##########
# set the log
logger = set_logging("API", "INFO")


# get the suspected & takedown cases from hades which have no polonius case number
df_db = get_cases(
    category=['"suspected counterfeiter"', '"takedown"'], Notthisuser='"upload"'
)

count_suspected = len(df_db[df_db["category"] == "suspected counterfeiter"].index)


if df_db.empty:

    logger.info(" No records to send to polonius")

else:

    if count_suspected > limit:

        # takedowns are unlimited onlz stop suspected counterfeiters of above the limit
        df_db = df_db[df_db["category"] == "takedown"]

        logger.warning(
            "%s suspected cases to process with a limit of %s cases. Please confirm these number of suspected cases are correct",
            str(count_suspected),
            str(limit),
        )

    # get header for API

    token = get_token(tokenurl, secret)
    if token:

        # send to polonius the cases

        for index, row in df_db.iterrows():

            businessUnit,category, price, quantity,  = get_product_details(
                row["business"]
            )
            if category:
                casePayload = get_casePayload(
                    row,businessUnit, category, price, quantity, 
                )

                if row.category == "suspected counterfeiter":
                    caseId = send_data(
                        Url=caseUrl, headers=token, casePayload=casePayload
                    )

                elif row.category == "takedown":
                    caseId = send_data(
                        Url=infringUrl, headers=token, casePayload=casePayload
                    )

                if caseId:

                    # update sql
                    try:
                        sql = (
                            "update advert set polonius_caseid="
                            + str(caseId["referenceNumber"])
                            + " where advert_id="
                            + str(row["advert_id"])
                        )

                        with engine.connect() as con:
                            result = con.execute(sql)

                        logger.info(
                            "sent case advert_id %s via API and got casenumber : %s",
                            str(row["advert_id"]),
                            str(caseId["referenceNumber"]),
                        )

                    except:
                        print(
                            "could not connect to sqlite database to update polonius_caseId ,see log"
                        )
                        logger.error(
                            "could not connect to sqlite database to update polonius_caseId with advert_id: %s",
                            str(row["advert_id"]),
                        )
                else:

                    print("problem with sending case to polonius ..see log")

                    logger.error(
                        "Problem with the Polonius API for advert_id: %s",
                        str(row["advert_id"]),
                    )
            else:
                print("error gettin product details see log")
                logger.error(
                    "Problem with getting product details for : %s and business %s",
                    str(row["advert_id"]),str(row["business"])
                            )

    else:
        print("problem getting token to access API --see log for details")

