from datetime import date


def is_business_day(d, holidays=(), observed=False):
    raise NotImplementedError


def add_business_days(d, n, holidays=(), observed=False):
    raise NotImplementedError


def business_days_between(a, b, holidays=(), observed=False):
    raise NotImplementedError
