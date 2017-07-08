# -*- coding: utf-8 -*-
"""
Created on 2017-7-7

@author: cheng.li
"""

from typing import Iterable
from typing import List
from typing import Dict
import numpy as np
import pandas as pd
import sqlalchemy as sa
from alphamind.data.engines.universe import Universe

risk_styles = ['BETA',
               'MOMENTUM',
               'SIZE',
               'EARNYILD',
               'RESVOL',
               'GROWTH',
               'BTOP',
               'LEVERAGE',
               'LIQUIDTY',
               'SIZENL',
               'COUNTRY']

industry_styles = [
    'Bank',
    'RealEstate',
    'Health',
    'Transportation',
    'Mining',
    'NonFerMetal',
    'HouseApp',
    'LeiService',
    'MachiEquip',
    'BuildDeco',
    'CommeTrade',
    'CONMAT',
    'Auto',
    'Textile',
    'FoodBever',
    'Electronics',
    'Computer',
    'LightIndus',
    'Utilities',
    'Telecom',
    'AgriForest',
    'CHEM',
    'Media',
    'IronSteel',
    'NonBankFinan',
    'ELECEQP',
    'AERODEF',
    'Conglomerates'
]


def append_industry_info(df):
    industry_arr = np.array(industry_styles)
    industry_codes = np.arange(len(industry_styles), dtype=int)
    industry_dummies = df[industry_styles].values.astype(bool)

    df['industry'], df['industry_code'] = [industry_arr[row][0] for row in industry_dummies], \
                                          [industry_codes[row][0] for row in industry_dummies]


class SqlEngine(object):
    def __init__(self,
                 db_url: str,
                 universe: Universe):
        self.engine = sa.create_engine(db_url)
        self.unv = universe

    def fetch_codes(self, ref_date: str) -> List[int]:

        def get_universe(univ, ref_date):
            univ_str = ','.join("'" + u + "'" for u in univ)
            sql = "select distinct Code from universe where Date = '{ref_date}' and universe in ({univ_str})".format(
                ref_date=ref_date, univ_str=univ_str)
            cursor = self.engine.execute(sql)
            codes_set = {c[0] for c in cursor.fetchall()}
            return codes_set

        codes_set = None

        if self.unv.include_universe:
            include_codes_set = get_universe(self.unv.include_universe, ref_date)
            codes_set = include_codes_set

        if self.unv.exclude_universe:
            exclude_codes_set = get_universe(self.unv.exclude_universe, ref_date)
            codes_set -= exclude_codes_set

        if self.unv.include_codes:
            codes_set = codes_set.union(self.unv.include_codes)

        if self.unv.exclude_codes:
            codes_set -= set(self.unv.exclude_codes)

        return sorted(codes_set)

    def fetch_data(self, ref_date,
                   factors: Iterable[str],
                   codes: Iterable[int],
                   benchmark: int = None,
                   risk_model: str = 'short') -> Dict[str, pd.DataFrame]:

        factor_str = ','.join('uqer.' + f for f in factors)

        total_risk_factors = risk_styles + industry_styles
        risk_str = ','.join('risk_exposure.' + f for f in total_risk_factors)

        special_risk_table = 'specific_risk_' + risk_model
        codes_str = ','.join(str(c) for c in codes)

        sql = "select uqer.Code, {factors}, {risks}, market.isOpen, daily_return.d1, {risk_table}.SRISK" \
              " from (uqer INNER JOIN" \
              " risk_exposure on uqer.Date = risk_exposure.Date and uqer.Code = risk_exposure.Code)" \
              " INNER JOIN market on uqer.Date = market.Date and uqer.Code = market.Code" \
              " INNER JOIN daily_return on uqer.Date = daily_return.Date and uqer.Code = daily_return.Code" \
              " INNER JOIN {risk_table} on uqer.Date = {risk_table}.Date and uqer.Code = {risk_table}.Code" \
              " where uqer.Date = '{ref_date}' and uqer.Code in ({codes})".format(factors=factor_str,
                                                                                  ref_date=ref_date,
                                                                                  codes=codes_str,
                                                                                  risks=risk_str,
                                                                                  risk_table=special_risk_table)

        factor_data = pd.read_sql(sql, self.engine)

        risk_cov_table = 'risk_cov_' + risk_model
        risk_str = ','.join(risk_cov_table + '.' + f for f in total_risk_factors)

        sql = "select FactorID, Factor, {risks} from {risk_table} where Date = '{ref_date}'".format(ref_date=ref_date,
                                                                                                    risks=risk_str,
                                                                                                    risk_table=risk_cov_table)

        risk_cov_data = pd.read_sql(sql, self.engine).sort_values('FactorID')

        total_data = {'factor': factor_data, 'risk_cov': risk_cov_data}

        if benchmark:
            sql = "select Code, weight / 100. as weight from index_components " \
                  "where Date = '{ref_date}' and indexCode = {benchmakr}".format(ref_date=ref_date,
                                                                                 benchmakr=benchmark)

            benchmark_data = pd.read_sql(sql, self.engine)
            total_data['benchmark'] = benchmark_data

        append_industry_info(factor_data)
        return total_data


if __name__ == '__main__':
    db_url = 'mysql+mysqldb://root:we083826@localhost/alpha?charset=utf8'
    universe = Universe(['zz500'])

    engine = SqlEngine(db_url, universe)
    ref_date = '2017-07-04'

    import datetime as dt

    start = dt.datetime.now()
    for i in range(500):
        codes = engine.fetch_codes('2017-07-04')
        total_data = engine.fetch_data(ref_date, ['EPS'], [1, 5], 905)

    print(dt.datetime.now() - start)

    print(total_data)
