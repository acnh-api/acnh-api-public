# © 2020 io mintz <io@mintz.cc>

import contextlib
import operator
import urllib.parse
from http import HTTPStatus
from functools import wraps
from typing import Union

import msgpack

from utils import config
from .. import utils
from ..common import acnh
from ..errors import (
	UnknownDesignCodeError,
	InvalidDesignCodeError,
	InvalidDesignError,
	DesignLitTheServerOnFireError,
)

DesignId = Union[str, int]

MAX_DESIGNS = 120
DESIGN_CODE_ALPHABET = InvalidDesignCodeError.DESIGN_CODE_ALPHABET
DESIGN_CODE_ALPHABET_VALUES = InvalidDesignCodeError.DESIGN_CODE_ALPHABET_VALUES

def design_id(design_code):
	code = design_code.replace('-', '')
	n = 0
	for c in code:
		n *= 30
		n += DESIGN_CODE_ALPHABET_VALUES[c]
	return n

def design_code(design_id):
	digits = []
	while design_id:
		design_id, digit = divmod(design_id, 30)
		digits.append(DESIGN_CODE_ALPHABET[digit])

	return add_hyphens(''.join(reversed(digits)).zfill(4 * 3))

def add_hyphens(author_id: str):
	return '-'.join(utils.chunked(author_id.zfill(4 * 3), 4))

def merge_headers(data, headers):
	data['author_name'] = headers['design_player_name']
	data['author_id'] = headers['design_player_id']
	data['created_at'] = headers['created_at']
	data['updated_at'] = headers['updated_at']

def accepts_design_id(func):
	@wraps(func)
	def wrapped(design_id_or_code: DesignId, *args, **kwargs):
		if isinstance(design_id_or_code, str):
			design_id_ = design_id(InvalidDesignCodeError.validate(design_id_or_code))
		else:
			design_id_ = design_id_or_code

		return func(design_id_, *args, **kwargs)

	return wrapped

@accepts_design_id
def download_design(design_id, partial=False):
	resp = acnh().request('GET', '/api/v2/designs', params={
		'offset': 0,
		'limit': 1,
		'q[design_id]': design_id,
	})
	resp.raise_for_status()
	resp = msgpack.loads(resp.content)

	if not resp['total']:
		raise UnknownDesignCodeError
	if resp['total'] > 1:
		raise RuntimeError('one ID requested, but more than one returned?!')
	headers = resp['headers'][0]
	if partial:
		return headers

	url = urllib.parse.urlparse(headers['body'])
	resp = acnh().request('GET', url.path + '?' + url.query)
	data = msgpack.loads(resp.content)
	merge_headers(data, headers)
	return data

def list_designs(author_id: int, *, pro: bool, with_binaries: bool = False):
	resp = acnh().request('GET', '/api/v2/designs', params={
		'offset': 0,
		'limit': 120,
		'q[player_id]': author_id,
		'q[pro]': 'true' if pro else 'false',
		'with_binaries': 'true' if with_binaries else 'false',
	})
	resp.raise_for_status()
	resp = msgpack.loads(resp.content)
	return resp

def stale_designs(needed, *, pro: bool):
	r = list_designs(config['acnh-design-creator-id'], pro=pro)
	free_slots = MAX_DESIGNS - r['count']
	if free_slots >= needed:
		return []
	return sorted(r['headers'], key=operator.itemgetter('created_at'))[:needed]

@accepts_design_id
def delete_design(design_id) -> None:
	resp = acnh().request('DELETE', f'/api/v1/designs/{design_id}')
	if resp.status_code == HTTPStatus.NOT_FOUND:
		raise UnknownDesignCodeError

design_errors = {
	HTTPStatus.BAD_REQUEST: InvalidDesignError,
	HTTPStatus.INTERNAL_SERVER_ERROR: DesignLitTheServerOnFireError,
}

def create_design(design_data) -> int:
	"""create a design. returns the created design ID."""
	resp = acnh().request('POST', '/api/v1/designs', data=msgpack.dumps(design_data))
	with contextlib.suppress(KeyError):
		raise design_errors[resp.status_code]
	resp.raise_for_status()
	data = msgpack.loads(resp.content)
	return data['id']
