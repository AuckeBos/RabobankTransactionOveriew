from BeautifulSoup import BeautifulSoup
import requests
from PIL import Image
from StringIO import StringIO
from datetime import datetime
import os.path
import json
import sys
import re


class Data(object):
    def __init__(self):
        self.session = requests.session()
        self.dataArray = []

    def getScid(self):
        request = self.session.get('https://bankieren.rabobank.nl/klanten/')
        soup = BeautifulSoup(request.content)
        return soup.find('input', {'id': 'Scid'})['value']

    def getImage(self, Scid, AuthId, AuthBpasNr):
        print 'a code is shown for account {} with card-number {}'.format(AuthId, AuthBpasNr)
        data = {'Scid': Scid, 'AuthId': AuthId, 'AuthBpasNr': AuthBpasNr}

        request = self.session.post('https://bankieren.rabobank.nl/klanten/qsl_setdebitcardforauth.do', data)
        soup = BeautifulSoup(request.content)

        imgURL = 'https://bankieren.rabobank.nl' + soup.find('img', {'id': 'scanner-code'})['src']
        request = self.session.get(imgURL)
        img = Image.open(StringIO(request.content))
        return img

    def checkCode(self):
        inlogcode = str(raw_input('Enter login code: '))
        if not re.match('^[0-9]{8}', inlogcode):
            print 'Your code should be 8 digits long, try again!'
            return self.checkCode()
        return inlogcode

    def login(self, Scid):
        inlogcode = self.checkCode()
        data = {'Scid': Scid, 'SessHrGebrChk': 'false', 'AuthCd': inlogcode, 'submit': 'Inloggen'}
        request = self.session.post('https://bankieren.rabobank.nl/klanten/qsl_validate.do', data)
        return BeautifulSoup(request.content)


    def getAccount(self, accounts):
        print 'Please choose your account by typing its row number:'
        for i in range(len(accounts)):
            print '{}. {}'.format(i, accounts[i]['accountNumber'])
        chosen = str(raw_input('Index of account: '))
        if len(accounts) < int(chosen) + 1:
            print 'non-valid index, please try again!'
            return self.getAccount(accounts)
        return accounts[int(chosen)]['index']

    def chooseAccount(self, mainPage):
        if mainPage.find('tbody', {'class': 'disable_dropdownScroll'}) == None:
            print 'login has failed, try again'
            return None
        accounts = []
        for row in mainPage.find('tbody', {'class': 'disable_dropdownScroll'}).findAll('tr'):
            link = str(row.find('a')['href'])
            index = link[link.index('=') + 1:]
            accountNumber = row.find('span', {'class': 'as_number'}).text
            accounts.append({'index': index, 'accountNumber': accountNumber})
        return self.getAccount(accounts)

    def advancedSearch(self, index, date):
        start = date
        month = int(date[5:7])
        if month == 2:
            s = '28'
        elif (month % 2 == 1 and month <= 7) or (month % 2 == 0 and month >=8):
            s = '31'
        else:
            s = '30'
        end = date[:8] + s
        request = self.session.get(
            'https://bankieren.rabobank.nl/klanten/particulieren/internetbankieren/betalensparen/default.html/'
            'transactionoverview-web/transaction-overview/961058994/ver=2.0/rparam=p7=' + end + '/rparam=p6=' + start +
            '/rparam=index=' + index + '/rparam=p1=false/rparam=render=transactionSearchResult.wsp/pparam=index=' +
            index)

        return BeautifulSoup(request.content), start, end

    def getTransactions(self, soup, index, start, end):
        table = soup.find('table', {'class': 'table_a '})
        rows = table.findAll('tr')
        for row in rows:
            self.dataArray.append(row)
        input = soup.find('input', {'class': 'next_search_information'})
        if input != None:
            nextSearchInfo = input['value']
            request = self.session.get(
                'https://bankieren.rabobank.nl/klanten/particulieren/internetbankieren/betalensparen/default.html/'
                'transactionoverview-web/transaction-overview/961058994/ver=2.0/resource/id=searchHistory/rparam=p7='
                + end + '/rparam=p6=' + start + '/rparam=index=' + index
                + '/rparam=p1=false/rparam=render=transactionSearchResult/rparam=p8.wsp/pparam=index' + index,
                params={'index': index, 'next_search_information': nextSearchInfo})
            soup = BeautifulSoup(request.content)
            self.getExtraTransactions(soup, index, start, end)
            self.dataArray.reverse()

    def getExtraTransactions(self, soup, index, start, end):
        div = soup.find('div', {'id': 'nextSearchInformationToBeUsed'})
        nextSearchInfo = div['data-next-search-information-to-be-used']
        table = soup.find('table')
        rows = table.findAll('tr')
        for row in rows:
            self.dataArray.append(row)
        if 'true' == div['data-overflow-indicator']:
            request = self.session.get(
                'https://bankieren.rabobank.nl/klanten/particulieren/internetbankieren/betalensparen/default.html'
                '/transactionoverview-web/transaction-overview/961058994/ver=2.0/resource/id=searchHistory/rparam=p7='
                + end + '/rparam=p6=' + start + '/rparam=index=' + index
                + '/rparam=p1=false/rparam=render=transactionSearchResult/rparam=p8.wsp/pparam=index' + index,
                params={'index': index, 'next_search_information': nextSearchInfo})
            self.getExtraTransactions(BeautifulSoup(request.content), index, start, end)


    def getCredits(self):
        if not os.path.exists('config.json'):
            file = open('config.json', 'w+')
            pattern = re.compile('^([a-zA-Z]{2}[0-9]{2}[a-zA-Z0-9]{4}[0-9]{8,10})$')
            inputAuthId = str(raw_input('Please enter your account number (iban): '))
            while not bool(pattern.match(inputAuthId)):
                inputAuthId = str(raw_input('Invalid, please enter a valid iban: '))
            AuthId = inputAuthId[9:12] + ' ' + inputAuthId[12:16] + ' ' + inputAuthId[16:]

            pattern = re.compile('^([0-9]{4})$')
            AuthBpasNr = str(raw_input('Please enter your card-number: '))
            while not bool(pattern.match(AuthBpasNr)):
                AuthBpasNr = str(raw_input('Invalid, please enter a valid card-number: '))

            data = {'AuthId':AuthId, 'AuthBpasNr':AuthBpasNr}

            if str(raw_input('Add accounts to exclude from overview? (y/n): ')) == 'y':
                data['exclude'] = self.getExcludedAccounts()
            else:
                print 'no excludes added'
                data['exclude'] = []
            json.dump(data, file)
            file.close()
            print('Config file created')
        data = json.load(open('config.json', 'r'))
        return data['AuthId'], data['AuthBpasNr'], data['exclude']


    def getExcludedAccounts(self):
        pattern = re.compile('^([a-zA-Z]{2}[0-9]{2}[a-zA-Z0-9]{4}[0-9]{8,10})$')
        array = []
        input = str(raw_input('Add iban to exclude: (press enter to finish) '))
        while input != '':
            if not bool(pattern.match(input)):
                input = str(raw_input('Invalid iban, please enter a valid iban to exclude (press enter to finish)'))
            else:
                parsed = input[0:4] + ' ' + input[4:8] + ' ' + input[8:12] + ' ' + input[12:16] + ' ' + input[16:]
                array.append(parsed)
                input = str(raw_input('Added, Add another iban to exclude: (press enter to finish) '))
        return array



    def getData(self, date):

        AuthId, AuthBpasNr, exclude = self.getCredits()

        img = self.getImage(self.getScid(), AuthId, AuthBpasNr)
        img.show()

        mainPage = self.login(self.getScid())

        index = self.chooseAccount(mainPage)
        if index == None:
            return Data().getData(date)

        soup, start, end = self.advancedSearch(index, date)

        self.getTransactions(soup, index, start, end)

        self.session.close()
        return self.dataArray, exclude
