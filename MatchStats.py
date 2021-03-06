# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""


import pandas as pd
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from bs4 import BeautifulSoup
import requests
import os.path


base_url = 'http://stats.ncaa.org'
#team_url = 'https://stats.ncaa.org/team/inst_team_list?academic_year=2020&conf_id=-1&division=1&sport_code=WVB'
team_url = 'https://stats.ncaa.org/team/inst_team_list?academic_year=2020&conf_id=-1&division=2&sport_code=WVB'
SEASONS = ['2019-20', '2018-19', '2017-18', '2016-17', '2015-16', '2014-15']
SEASONS = ['2019-20', '2018-19', '2017-18', '2016-17', '2015-16']


def get_all_teams(tm_url):
    '''
    
    Extract all team names and team URLs from the given team page
    '''
    
    response = requests.get(tm_url)
    soup = BeautifulSoup(response.text, 'lxml')

    tbs = pd.read_html(response.text)
    df = pd.concat(tbs[1:]).reset_index(drop=True)
    df.columns = ['Team']

    df['Team URL'] = [soup.find('a', text=row['Team']).get('href') for _,row in df.iterrows()]

    return df


def get_match_stats(row, driver):
    driver.get(base_url + row['Team URL'])
    
    try:
        game_by_game = driver.find_element_by_link_text('Game By Game')
        game_by_game.click()
    except:
        print('Unable to find Game by Game for %s on %s' % (row['Team'], base_url + row['Team URL']))
        return pd.DataFrame([])
    
    dfs = pd.read_html(driver.page_source)
    
    all_seasons = []
    for season in SEASONS:
        if season != SEASONS[0]:
            try:
                year_link = driver.find_element_by_link_text(season)
                year_link.click()
            except:
                continue

        dfs = pd.read_html(driver.page_source)
        
        '''
            The last row may contain comments in rare cases
            Check of this and ignore this row
        '''
        last_row = len(dfs[3].index)
        if dfs[3].iloc[last_row-1,0][0] == '*':
            last_row -= 1

        match = dfs[3].iloc[2:last_row,:-1].reset_index(drop=True)
        match.columns = dfs[3].iloc[1,:-1].values
        match.rename(index=str, columns={'Pct' : 'Hit Pct'}, inplace=True)

        for unneeded in ['Attend', 'MP', 'MS']:
            if unneeded in match.columns:
                match.drop(unneeded, axis=1, inplace=True)
            
        # remove matchs with no reported result
        match = match[match['Result'].str.contains('W|L', regex=True)]

        all_seasons.append(match)
        
    match_results = pd.concat(all_seasons, sort=False)
    
    match_results.insert(0, 'Team', row['Team'])
    match_results.loc[:,'S':'BHE'] = match_results.loc[:,'S':'BHE'].fillna(0, axis=1)
    match_results.loc[:,'S':'BHE'] = match_results.loc[:,'S':'BHE'].astype('str').apply(lambda x: x.str.rstrip('\*\/'))

    int_cols = ['S', 'Kills', 'Errors', 'Total Attacks', 'Assists', 'Aces', 'SErr',
                'Digs', 'RErr', 'Block Solos', 'Block Assists', 'BErr', 'BHE']
    float_cols = ['Hit Pct', 'PTS']

    match_results[int_cols] = match_results[int_cols].astype('int')
    match_results[float_cols] = match_results[float_cols].astype('float')

    temp = match_results['Result'].str.split(expand=True)
    if len(temp.columns) == 2:
        match_results['Match Result'] = temp[0]
        match_results[['Sets Won', 'Sets Lost']] = temp[1].str.split('-', expand=True).astype('int')

    elif (len(temp.columns) == 3):
        match_results['Sets Won'] = temp[0].astype('int')
        match_results['Sets Lost'] = temp[2].astype('int')
        match_results['Match Result'] = 'W'
        match_results[match_results['Sets Lost'] > match_results['Sets Won']] = 'L'

    elif (len(temp.columns) == 4):
        match_results['Sets Won'] = temp[1].astype('int')
        match_results['Sets Lost'] = temp[3].astype('int')
        match_results['Match Result'] = temp[0]

    match_results.drop('Result', axis=1, inplace=True)

    # create the home/away columm
    match_results.insert(1, 'Location', 'Home')
    match_results.loc[match_results['Opponent'].str.startswith('@'), 'Location'] = 'Away'
    match_results['Opponent'] = match_results['Opponent'].str.lstrip('@ ',)

    # handle nuetral locations
    neutral_ix = match_results[match_results['Opponent'].str.contains(' @')].index
    if not neutral_ix.empty:
        match_results.loc[neutral_ix, 'Opponent'] = match_results.loc[neutral_ix, 'Opponent'].str.split('@', expand=True)[0]
        match_results.loc[neutral_ix, 'Location'] = 'Neutral'
    match_results['Opponent'] = match_results['Opponent'].str.strip()
    
    return match_results


def get_team_roster(row, driver):
    driver.get(base_url + row['Team URL'])

    all_seasons = []
    for season in SEASONS:
        if season != SEASONS[0]:
            select = Select(driver.find_element_by_id('year_list'))
            select.select_by_visible_text(season)

        try:
            game_by_game = driver.find_element_by_link_text('Roster')
            game_by_game.click()

            roster = pd.read_html(driver.page_source)[0]
            roster.columns = roster.columns.droplevel(0)
            roster.insert(0, 'Team', row['Team'])
            roster.insert(1, 'Season', season)
        except:
            print('Unable to find Roster for %s on %s' % (row['Team'], base_url + row['Team URL']))
            roster = pd.DataFrame()
        
        all_seasons.append(roster)
        
    all_rosters = pd.concat(all_seasons).reset_index(drop=True)
    return all_rosters



if os.path.exists('D2Teams2020.csv'):
    dash = pd.read_csv('D2Teams2020.csv')
else:
    dash = get_all_teams(team_url)
    dash.to_csv('D2Teams2020.csv', index=False)

driver = webdriver.Chrome()
results = []

'''
Roster
'''
# for _,row in dash.iterrows():
#     tmp = get_team_roster(row, driver)
#     if not tmp.empty:
#         results.append(tmp)
# df = pd.concat(results).reset_index(drop=True)        
# df[['Last', 'First']] = df['Player'].str.split(',', expand=True)
# df['Year'] = df['Season'].str.split('-').str.get(0)


for _,row in dash.iterrows():
# for _,row in dash.iloc[137:138,:].iterrows():
    tmp = get_match_stats(row, driver)
    if not tmp.empty:
        results.append(tmp)
        
driver.close()

df = pd.concat(results).reset_index(drop=True)        
df.info()
df.to_csv('D2MatchResults.csv', index=False)