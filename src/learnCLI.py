from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
import glob
import dropbox
import time
import sys
import re
import os

class LearnCLI:

	def __init__(self, username, password, path) :
		self.username = username
		self.password = password
		self.path = path
		self.url = "https://learn.uwaterloo.ca"
		self.filesInCurrentDirectory = []
		# list of browsers these are URLs
		# URL possibilities: [{home}, {courses}, {grades, announcements, content}, {if content: }]
		self.pageHistory = []
		# list of files.
		self.fileHistory = []
		# True if grade page has been already loaded in browser. Otherwise False.
		self.gradeLoaded = False
		# True if content page has been already loaded in browser. Otherwise False.
		self.contentLoaded = False
		# preferences for chrome driver
		self.prefs = {}
		# Dropbox instance. If already authenticated it will hold an instance. Otherwise None.
		self.getDropboxAuth()


	def getDropboxAuth(self) :
		try :
			file = open("../d2d.auth", "r")
			self.dbx = dropbox.Dropbox(file.read())
		except Exception :
			self.dbx = None

	def login(self) :
		xpaths = { 'usernameTxtBox' : "//input[@name='username']",
				   'passwordTxtBox' : "//input[@name='password']",
				   'submitButton' : "//input[@name='submit']"
				 }
		try:
			# Set driver preferences
			chromeOptions = webdriver.ChromeOptions()
			chromeOptions.add_argument("--log-level=3")
			with open("../d2d.config") as f :
				for line in f.read().splitlines() :
					if line.strip() == "" : 
						continue
					try :
						d2dProperty = line.split("=")
						self.prefs[d2dProperty[0].strip()] = d2dProperty[1].strip()
					except Exception :
						print("Please define d2d configuration propertly.")

			chromeOptions.add_experimental_option("prefs", self.prefs)

			browser = webdriver.Chrome(executable_path = self.path, chrome_options = chromeOptions)
			# Set browser size before doing get. This is to avoid 'Element is not currently visible and may not be manipulated' exception
			browser.set_window_size(1000,1000)
			# Make browser not visible to users. We can use headless chrome but https://bugs.chromium.org/p/chromedriver/issues/detail?id=1973 doesn't allow headless chromes to download files.
			browser.set_window_position(-10000,0)
			browser.get(self.url)

			# Output Message
			print("Logging in to " + self.url + "...")

			# Clear the username textbox if already allowed by "Remember me".
			browser.find_element_by_xpath(xpaths['usernameTxtBox']).clear()

			# Write username in Username textbox
			browser.find_element_by_xpath(xpaths['usernameTxtBox']).send_keys(self.username)

			# Clear password textbox if already allowed by "Remember me"
			browser.find_element_by_xpath(xpaths['passwordTxtBox']).clear()

			# Write password in Password textbox
			browser.find_element_by_xpath(xpaths['passwordTxtBox']).send_keys(self.password)

			# Click login button
			browser.find_element_by_xpath(xpaths['submitButton']).click()

			# Check if its login credentials is correct
			if browser.current_url != self.url + "/d2l/home" :
				print("Error: Invalid username or password")
				sys.exit(2)

			# Output Message
			print("Logged in.")

			self.browser = browser
			self.pageHistory.append(self.browser.current_url)

		except KeyboardInterrupt:
			browser.close()

	def getContent(self) :
		# This is the element which lists all the courses 
		# (Can't use BeautifulSoup or MechanicalSoup due to new learn updates)
		courses = "//a[@class='d2l-image-tile-base-link style-scope d2l-image-tile-base']"

		# Increasing time will guarantee javascript loading but 10 sec should be enough in most cases.
		time.sleep(1)
		self.load(courses, 10)

		courseElements = self.browser.find_elements_by_xpath(courses)
		courseInfoDict = {}

		for course in courseElements:
			# print('Adding ' + course.text + ' and ' + course.get_attribute("href"))
			courseInfoDict[course.text.strip()] = course.get_attribute("href")

		self.courseInfoDict = courseInfoDict

	# Method to wait until condition is loaded
	def load(self, xpath, timeout) :
		try:
			element_present = EC.presence_of_element_located((By.XPATH, xpath))
			WebDriverWait(self.browser, timeout).until(element_present)
			time.sleep(1)
		except TimeoutException:
   			print("Timed out waiting for page to load")

   	# Method to find out URLs for announcement, grades and content
   	# Returns KVP in the form of {[grades, url], [content, url]}
	def specificCourseHome(self) :
		toRet = {}
		xpath = "//a[@class='d2l-navigation-s-link']"	
		self.load(xpath, 5)

		elements = self.browser.find_elements_by_xpath(xpath)

		for element in elements :
				text = element.text.strip()
				if text == "Grades" or text == "Content" :
					toRet[text] = element.get_attribute("href")

		self.filesInCurrentDirectory = []
		for key in toRet :
			self.filesInCurrentDirectory.append(key)
		self.gradeContent = toRet

	# This method is basically called when app logged into learn and lists all the courses and commands available.
	# This is only called once.
	def getCourseHome(self) :
		toPrint = self.getCommands()

		# print for init.
		toPrint += "\nList of all the courses:\n"

		# for each course, open the URI.
		for courseName in self.courseInfoDict :
			toPrint += "- " + courseName + "\n"
			self.filesInCurrentDirectory.append(courseName)
		self.fileHistory.append(self.filesInCurrentDirectory)
		print(toPrint)

	# This method is basically help command.
	def getCommands(self) :
		toRet = "\nList of available commands:\n"

		toRet += "- h: help\n"
		toRet += "- q: quit\n"
		toRet += "- ls: list all files in current directory\n"
		toRet += "- cd: change directory\n"
		toRet += "- d2d: downloads specified file and drops it to your dropbox (Regex supported)\n"

		return toRet

	# Method to print files in current directory
	def lsCommand(self) :
		toPrint = "\nFiles in current directory:\n"
		for file in self.filesInCurrentDirectory :
			toPrint += "- " + file + "\n"
		print(toPrint)

	# Method to change directory.
	def cdCommand(self, commands) :
		directory = ""
		for c in commands :
			directory += " " + c
		directory = directory.strip()

		size = len(self.pageHistory)

		if directory == ".." :
			if size == 1 :
				print("This is the home directory")
			else :	
				self.browser.get(self.pageHistory[size - 2])
				self.filesInCurrentDirectory = self.fileHistory[size - 2]
				self.pageHistory.pop()
				self.fileHistory.pop()
				# Debugging purpose
				print(self.pageHistory[size - 2])
		elif directory in self.filesInCurrentDirectory :
			link = None
			if size == 1 :
				link = self.courseInfoDict[directory]
				self.browser.get(link)
				#Debugging purpose
				# print(self.browser.current_url)
				self.specificCourseHome()
			if size == 2 :
				link = self.gradeContent[directory]
				self.filesInCurrentDirectory = []
				self.browser.get(link)
				if directory == "Grades" :
					self.getFilesInCurrentDirectoryGrades()
				if directory == "Content" :
					self.getFilesInCurrentDirectoryContent()
			self.pageHistory.append(link)
			self.fileHistory.append(self.filesInCurrentDirectory)
			# Debugging purpose
			# print(link)
		else :
			print(directory + " does not exist")


	def getFilesInCurrentDirectoryGrades(self) :
		timeSec = 3
		if self.gradeLoaded :
			timeSec = 1
		# time.sleep(timeSec)
		gradesTableXpath = "//div[@class='d2l-grid-container']"
		tableRowXpath = "//tr"
		tableColTextXpath = "//label"
		self.load(gradesTableXpath, timeSec)
		self.gradeLoaded = True

		tableRows = self.browser.find_elements_by_xpath(tableRowXpath)

		if len(tableRows) == 1 : 
			return

		print("\n-------------------------------------------------")
		i = 0
		for tableRow in tableRows :
			if i > 0 :
				print(tableRow.text)
				print("-------------------------------------------------")
			i = i + 1

	def getFilesInCurrentDirectoryContent(self) :
		timeSec = 8
		if self.contentLoaded :
			timeSec = 2
		# time.sleep(2)
		listXpath = "//li"
		listTableXpath = "//div[@class='d2l-twopanelselector-side-padding']"
		tableOfContentXpath = "//ul//ul//li[contains(@class, 'd2l-datalist-item') and contains(@class ,'d2l-datalist-simpleitem')]"
		self.load(listTableXpath, timeSec)
		self.contentLoaded = True

		dirList = self.browser.find_elements_by_xpath(listXpath)

		for directory in dirList :
			if directory.text.startswith("Table of Contents") :
				directory.click()
				# time.sleep(timeSec)
				self.load(tableOfContentXpath, timeSec)
				time.sleep(2)
				tableOfContent = self.browser.find_elements_by_xpath(tableOfContentXpath)
				for file in tableOfContent :
					fileName = file.text.strip()
					if fileName != "" and self.isNotExcluded(fileName):
						self.filesInCurrentDirectory.append(fileName.splitlines()[0])
				break

	def isNotExcluded(self, fileName) :
			return not (fileName.endswith("Link") or fileName.endswith("External Learning Tool") or fileName.endswith("Web Page") or fileName.endswith("Quiz"))

	def getInput(self) :
		command = ""
		while command != "q" :
			command = input(">>> ").strip()
			self.processInput(command)

	def processInput(self, commands) :
		command = re.split(r'\s{1,}', commands)
		if command[0] == "ls":
			self.lsCommand()
		elif command[0] == "cd":
			self.cdCommand(command[1:])
		elif command[0] == "d2d":
			fileNames = self.downloadFile(command[1:])
			self.uploadToDropbox(fileNames)
		elif command[0] == "h":
			print(self.getCommands())
		elif command[0] == "q":
			#do nothing
			print("Exiting...")
		else :
			print("Unknown command. Please type h to see list of commands available")

	# Files can be comma seprated to indicate multiple files.
	# Maybe support regex later.
	def downloadFile(self, files) :
		if len(files) == 0 :
			return

		directory = ""
		for c in files :
			directory += " " + c
		fileNames = [x.strip() for x in directory.split(',')]
		ret = []

		tableOfContentActionXpath = "//ul//ul//li[contains(@class, 'd2l-datalist-item') and contains(@class ,'d2l-datalist-simpleitem')]"
		downloadXpath = ".//a[@class=' vui-dropdown-menu-item-link']"

		try:
			listOfFiles = self.browser.find_elements_by_xpath(tableOfContentActionXpath)
		except Exception:
			print("Please call d2d in Content directory.")

		downloadedFiles = []
		for file in listOfFiles :
			fileName = self.isToDownload(file, fileNames)
			if fileName != None :
				try:
					file.find_element_by_xpath(".//a[@class='d2l-contextmenu-ph']").click()
					self.load(".//a[@class='d2l-contextmenu-ph']", 3)
					actions = file.find_elements_by_xpath(downloadXpath)
					for action in actions :
						if action.text.strip() == "Download" :
							action.click()
					ret.append(fileName)
				except Exception:
					print("Could not download " + fileName + ".")

		return ret

	def isToDownload(self, file, fileNames) :
		fileText = file.text.strip().splitlines()[0].strip()
		for fileName in fileNames :
			m = re.search(fileName, fileText) 
			if m == None :
				return None
			start, end = re.search(fileName, fileText).span()
			if (start > 0 or end > 0) and fileText in self.filesInCurrentDirectory :
				return fileText
		return None

	def uploadToDropbox(self, fileNames) :
		for fileName in fileNames :
			try :
				totalWaitTime = 0
				fileRegex = self.prefs["download.default_directory"] + "/" + fileName + "*"
				downloadedFiles = glob.glob(fileRegex)

				# Wait until download started
				while len(downloadedFiles) == 0 :
					time.sleep(1)
					totalWaitTime += 1
					if totalWaitTime == 60 :
						print("Timeout")
						return
					downloadedFiles = glob.glob(fileRegex)

				# Wait until .crdownload disappeared (meaning download completed)
				while len(glob.glob(fileRegex)) > 0 and glob.glob(fileRegex)[0].endswith("crdownload") :
						time.sleep(1)
						totalWaitTime += 1
						if totalWaitTime == 60 :
							print("Timeout")
							return
						continue
				downloadedFile = glob.glob(fileRegex)[0]
				downloadedFileName = downloadedFile[downloadedFile.index(fileName):]
				f = open(downloadedFile, 'rb')

				print("Dropping " + downloadedFile + " to Dropbox")
				# Actually drop the file into dropbox
				self.dbx.files_upload(f.read(), "/learnCLI/" + downloadedFileName, mode = dropbox.files.WriteMode('overwrite') ,mute = True)
				print("Dropped " + downloadedFile + " to Dropbox")
			except Exception :
				print("Could not upload " + fileName + " to dropbox.")
				continue

	def tearDown(self) :
		self.browser.close()
		