# Original Author: Thomas Eady, Good Program Web Services 2018"

## ---------- DEPENDENCIES

import requests
import base64
import re
import pprint
import time
import os
import json

from colorama import Fore, Back, Style
from bs4 import BeautifulSoup as bs

from ebaysdk.finding import Connection as finding
from ebaysdk.shopping import Connection as shopping


## ---------- GV's

pp = pprint.PrettyPrinter(indent=4)

limit = 300
SLEEP_INTERVAL = 120 # 2 minutes

DEV_MODE = True

inputIndicator = "[ ?? ] "
runningIndicator = "[ .. ] "
errorIndicator = "[ !! ] "
message = "[ >> ] "

ebayUrl = ""
ebayDataRaw = None
ebayProducts = []
ebayStoreName = os.environ['ebayStoreName'] 
ebayApi = None
ebaySiteId = "EBAY-AU" 									#Change according to your locale
ebayAppId = os.environ['ebayAppId']

shopifyAPIKey = os.environ['shopifyAPIKey'] 
shopifyAPIPassword = os.environ['shopifyAPIPassword']
shopifyStoreName = os.environ['shopifyStoreName'] 		#https://  -->   name  <--   .myshopify.com/admin/products.json

## ---------- FUNCTIONS

def getExistingShopifyProducts():
	""" Get all existing shopify products """

	funId = "[ getShopifyProd ]"
	if DEV_MODE: print(funId + message + 'Looking for existing Shopify products' + Style.RESET_ALL)

	try:
		auth = shopifyAPIKey + ":" + shopifyAPIPassword 

		headers = {
			'Content-Type': 'application/json',
			'Authorization': 'Basic {token}'.format(token=base64.b64encode(auth.encode()).decode('ascii'))
		}

		url = 'https://'+ shopifyStoreName +'.myshopify.com/admin/products.json?limit=' + limit

		shopifyExistingProductsTemp = requests.get(url, headers=headers)
		shopifyExistingProductsTemp = json.loads(shopifyExistingProductsTemp.text)


		shopifyExistingProducts = []

		count = 0

		for row in shopifyExistingProductsTemp['products']:

			productBlock = {}

			productBlock['title'] = row['title']
			productBlock['id'] = row['id']
			productBlock['price'] = row['variants'][0]['price']
			productBlock['variants'] = row['variants']
			productBlock['body_html'] = row['body_html']
			shopifyExistingProducts.append(productBlock)
		
		if DEV_MODE: print(funId + message + 'Found ' + str(len(shopifyExistingProducts)) + ' products' + Style.RESET_ALL)
		return shopifyExistingProducts
		
	except Exception as e:
		if DEV_MODE: print(funId + errorIndicator + 'Error getting shopify products: ' + str(e) + Style.RESET_ALL)
		raise str(e)

def updateExistingShopifyProduct(product):
	""" Update existing product on shopify if a match is found """

	funId = "[ updateProd ]"

	auth = shopifyAPIKey + ":" + shopifyAPIPassword 

	headers = {
	    'Content-Type': 'application/json',
	    'Authorization': 'Basic {token}'.format(token=base64.b64encode(auth.encode()).decode('ascii'))
	}

	url = 'https://' + shopifyStoreName + '.myshopify.com/admin/products/' + str(product['id']) + '.json'


	data = {
		"product": {
			"id": str(product['id']),
			"body_html": str(product['description']),
			"variants": [
				{
					"id": product['variants'][0]['id'],
					"price": product['price'],
					"sku": product['variants'][0]['sku']
				}
			]
		}
	}

	response = requests.put(url, headers=headers, data=json.dumps(data)) # Add new product

	if DEV_MODE: print(funId + message + Fore.GREEN + "Done." + Style.RESET_ALL)


def addNewProduct(product):
	""" Insert new product to shopify store """

	funId = "[ addProd ]"

	auth = shopifyAPIKey + ":" + shopifyAPIPassword 

	headers = {
	    'Content-Type': 'application/json',
	    'Authorization': 'Basic {token}'.format(token=base64.b64encode(auth.encode()).decode('ascii'))
	}

	url = 'https://' + shopifyStoreName + '.myshopify.com/admin/products.json'

	images = []

	for row in product["data"]["images"]:
		images.append({
				"src": row
			})

	data = {
		"product": {
			"images": images, 
			"title": product['name'],
			"body_html": product['data']['description'],
			"vendor": ebayStoreName,
			"product_type": "Other",
			"tags": "",
			"published_scope": "global",
			"variants": [
				{
					"price": product['data']['price'],
					"inventory_quantity": int(product["data"]["quantity"]),
					"inventory_management": "shopify",
					"requires_shipping": True
				}
			],
		    "published": True
		}
	}

	response = requests.post(url, headers=headers, data=json.dumps(data)) # Add new product

	if DEV_MODE: print(funId + message + Fore.GREEN + "Done." + Style.RESET_ALL)

def getExtraData(productLink, itemId):
	""" Get shopping data from from Ebay API (description & details) """

	funId = "[ extraData ]"

	data = {}

	if DEV_MODE: print(funId + runningIndicator + "finding extra data for: " + productLink)

	shoppingEbayApi = shopping(siteid = ebaySiteId, appid = ebayAppId, config_file=None)
	shoppingEbayApi.execute('GetSingleItem', {'IncludeSelector': 'Description, Details', 'ItemID': str(itemId)})
	item = shoppingEbayApi.response.dict()
	prodData = item['Item']

	#pp.pif DEV_MODE: print(prodData)

	data['images'] = prodData['PictureURL']
	data['description'] = prodData['Description']
	data['quantity'] = prodData['Quantity']
	data['price'] = prodData['CurrentPrice']['value']
	data['price_currency'] = prodData['CurrentPrice']['_currencyID']

	return data


def getEbayProductData():
	""" Gather all ebay product data from given store """
	funId = "[ ebayProdData ]"

	if DEV_MODE: print(funId + runningIndicator + "Searching: " + ebayStoreName)

	total = 0

	try:
		findingEbayApi = finding(siteid = ebaySiteId, appid = ebayAppId, config_file=None)
		findingEbayApi.execute('findItemsIneBayStores', {'storeName': ebayStoreName, 'IncludeSelector':['Title']})
		item = findingEbayApi.response.dict()
		data = item["searchResult"]["item"]
		total = str(len(data))
		if DEV_MODE: print(funId + message + Fore.GREEN + "Successfully found " + total + " products." + Style.RESET_ALL)
	except Exception as e:
		if DEV_MODE: print(str(e))
		return

	if DEV_MODE: print(funId + runningIndicator + "Proccessing products...")

	products = []

	count = 0

	for product in data:

		if DEV_MODE: print(runningIndicator + str(count) + "/" + total)

		productBlock = {}

		productBlock["name"] = product['title']
		productBlock["ebayLink"] = product['viewItemURL']

		productBlock["data"] = getExtraData( productBlock["ebayLink"], product['itemId'] )

		products.append(productBlock)

		if len(productBlock["data"]["description"]) > 1:
			desc = "desc found"
		else:
			desc = "desc not found"

		if DEV_MODE: print("   |____ Name: " + str(productBlock["name"]) + "\n   |____ Price: " + str(productBlock["data"]["price"]) + "\n   |____ Description: " + desc + "\n   |____ Images: " + str(productBlock["data"]["images"]) )

		if count >= limit:
			break

		count += 1

	if DEV_MODE: print(Style.RESET_ALL + funId + message + "Finished Cleaning Data")

	return products

def syncAll(productData):
	""" Synchronise all new products """
	funId = "[ syncAll ]"
	if DEV_MODE: print(runningIndicator + "Getting existing shopify products")

	existingShopifyProducts = getExistingShopifyProducts()
	if DEV_MODE: print(funId + 'FOUND ' + str(existingShopifyProducts) + " existing shopify products" )

	if DEV_MODE: print(message + "Products Found: ")

	for row in existingShopifyProducts:
		if DEV_MODE: print("   |____ " + str(row['id']) + " " + row['title'])

	if DEV_MODE: print(message + "Beginning product sync...")

	count = 0

	toProcess = {
	}
	toProcess['toAdd'] = []
	toProcess['toUpdate'] = []

	for product in productData:

		if DEV_MODE: print(funId + runningIndicator + "Syncing: " + str(product['name']))

		matchFound = False
		updateShopifyProduct = {}

		productTitle = product['name'].replace(" ", "").upper()

		for row in existingShopifyProducts:
			rowTitle = row['title'].replace(" ", "").upper()
			if DEV_MODE: print(funId + 'TESTING IF: ' + productTitle + ' = ' + rowTitle  + Style.RESET_ALL)

			if rowTitle == productTitle:
				if DEV_MODE: print(funId + Fore.GREEN + Style.BRIGHT + "Found"  + Style.RESET_ALL)
				matchFound = True
				if float(row['price']) != float(product['data']['price']): #or str(row['body_html']) != str(product['data']['description']):
					updateShopifyProduct = row
					updateShopifyProduct['price'] = product['data']['price']
					updateShopifyProduct['description'] = product['data']['description']
				break

		if not matchFound: 
			if DEV_MODE: print(funId + message + Fore.GREEN + "No match found, adding new product" + Style.RESET_ALL)
			toProcess['toAdd'].append(product)
		else:
			if updateShopifyProduct:
				toProcess['toUpdate'].append(updateShopifyProduct)
				if DEV_MODE: print(funId + message + Fore.GREEN + "Match Found but prices out of sync...updating shopfiy price..." + Style.RESET_ALL)
			else:
				if DEV_MODE: print(funId + message + Fore.YELLOW + "Product title and price matches existing shopify title, moving on..." + Style.RESET_ALL)

		count+= 1
		if count >= limit:
			break

	# Add all new products
	if DEV_MODE: print(funId + 'Products to add: ' + str(len(toProcess['toAdd'])))
	for tAdd in toProcess['toAdd']:
		if DEV_MODE: print(funId + tAdd['name'])
		addNewProduct(tAdd)

	# Update existing products
	if DEV_MODE: print(funId + 'products to update: ' + str(len(toProcess['toUpdate'])))
	for tUp in toProcess['toUpdate']:
		if DEV_MODE: print(funId + tUp['title'])
		updateExistingShopifyProduct(tUp)

def end():
	""" Kill """
	if DEV_MODE: print(Style.RESET_ALL)
	exit()

def main():
	""" Initialise sync and main while loop """

	funId = "[ main ]"

	print(Style.RESET_ALL)
	print("Launching...")

	errors = 0

	while True:
		try:
			productData = getEbayProductData()
			syncAll(productData)
			print(funId + 'Full process complete, no errors')
		except:
			errors += 1
			print(funId + 'Process error raised...restarting.')
		print(funId + 'Total Errors: ' + str(errors))
		print('Sleeping...')
		time.sleep(SLEEP_INTERVAL)
		print('Waking...')
	
	end()
	


## ---------- LAUNCH

if __name__ == '__main__':
	main()