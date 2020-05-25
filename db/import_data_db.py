#script to import data from the splunk online report 
# into hades db on sqlite 


#TODO Sqlite admin : run an Sqlite backup before import ..schedule on server or create a script ? 

#TODO add in a region if none - Faustas = Done

#TODO check if seller and domain is a false positive if yes do not import and discard 

#TODO check if seller and domain is in the database if so then update previous category


import pandas as pd
import numpy as np
import datetime

from sqlalchemy.types import Integer,Text
from sqlalchemy import create_engine
engine = create_engine('sqlite:///HadesV2App/db/hades.db', echo=True)


#getting the advert table and convert into a dataframe ... 
df_db=pd.read_sql('SELECT * FROM advert', engine)


#we need to change this to collect the file from where splunk saves it 
import_file='c:\sqlite\db\online.csv'

#importing a file with countries and regions that will be joined with the main database - F
df_region=('c:\sqlite\db\regioncountry.csv', keep_default_na=False, na_values=['_'])

#We can continue with this intially if we have problems importing with pandas we can use the GUI to import
export_file='c:\sqlite\db\online_transformed.csv'

#These are the columns only needed for the export to csv file 
export_cols=['advert_id','region', 'country', 'product', 'price', 'cur', 'seller',
       'category', 'last_seen', 'cat', 'domain', 'url',
       'date_found', 'business', 'product_brand','polonius_caseid','updated_date','updated_by']


#we need to rename the columns as they are different in the splunk report , plus whilst
#merging new columns are created 
rename_cols={'Product_category_for_polonius':'product_brand','Business':'business',
                    'report_date':'date_found','cat_y':'cat','region_y':'region', 'country_y':'country', 
                    'price_y':'price','cur_y':'cur', 'category_y':'category', 'last_seen_y':'last_seen', 'url_y':'url'
            }

#Lets drop all the useless columns from the merge and the splunk report 
columns_drop=['advert_id', 'region_x', 'country_x', 'price_x', 'cur_x',
               'category_x', 'last_seen_x', 'cat_x', 'url_x',
              'date_found', 'business', 'product_brand', 'polonius_caseid',
                     'updated_date', 'updated_by','_merge']


#read in the csv from splunk
df=pd.read_csv(import_file)
print(df.head())

#merging df with country and region database, renaming the column back into "region" - F
df=pd.merge(df, df_region, on='country', how='left')
df=df.rename(columns={'region_y':'region')
                      
#drop some more useless columns before we merge 
df.drop(['score','set_category'], axis=1,inplace=True)

#merge so we only get new adverts .New adverts=new seller + domain + product
df_merge=df_db.merge(df,indicator=True,how='outer',on=['seller','product','domain'])

#take only the right sided ones . these are adverts that are not in the sqlite database ..i.e the new ones
df=df_merge[df_merge['_merge']=='right_only']

#drop all the useless columns created by the merge .. i.e the adverts already in database
df.drop(columns_drop,axis=1,inplace=True)


#this is for SQLite rowid which is a primary key, send in a null object and sqlite will sort this out
df.loc[:,'advert_id']=None


#make polonius_caseid null
df.loc[:,'polonius_caseid']=None



#set that the "upload user " has updated 
df.loc[:,'updated_by']='upload'
#and when uploaded
df.loc[:,'updated_date']=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#rename the columns so it fits the table columns
df=df.rename(columns=rename_cols)

#set category to lowercase 
df['category']=df['category'].str.lower()


#write out the csv to be uploaded ..this is now just a backup 
df.to_csv(export_file,index=False, columns=export_cols)

#write the adverts back to the table "advert" as one big hit 
df.to_sql('advert', con=engine, if_exists='append',
          index=False,dtype={"business": Text(),"product_brand":Text()})
