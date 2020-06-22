# © 2020 io mintz <io@mintz.cc>

import re
from http import HTTPStatus
from typing import ClassVar, List, TYPE_CHECKING

from .designs.format import PALETTE_SIZE, MAX_DESIGN_TILES, BYTES_PER_PIXEL

if TYPE_CHECKING:
	from .designs.encode import Layer

class ACNHError(Exception):
	code: ClassVar[int]
	message: ClassVar[str]
	http_status: ClassVar[int]

	def __int__(self):
		return self.code

	def to_dict(self):
		return {'error': self.message, 'error_code': self.code, 'http_status': self.http_status}

class InvalidFormatError(ACNHError):
	http_status = HTTPStatus.BAD_REQUEST
	regex: re.Pattern

	def to_dict(self):
		d = super().to_dict()
		d['validation_regex'] = self.regex.pattern
		return d

	@classmethod
	def validate(cls, s):
		if not cls.regex.fullmatch(s):
			raise cls
		return s

class DodoCodeError(ACNHError):
	pass

class UnknownDodoCodeError(DodoCodeError):
	code = 101
	http_status = HTTPStatus.NOT_FOUND
	message = 'unknown dodo code'

class InvalidDodoCodeError(DodoCodeError, InvalidFormatError):
	code = 102
	message = 'invalid dodo code'
	regex = re.compile('[A-HJ-NP-Y0-9]{5}')

class ImageError(ACNHError):
	pass

class DesignError(ACNHError):
	pass

class UnknownDesignCodeError(DesignError):
	code = 201
	message = 'unknown design code'
	http_status = HTTPStatus.NOT_FOUND

class InvalidDesignCodeError(DesignError, InvalidFormatError):
	code = 202
	message = 'invalid design code'

	DESIGN_CODE_ALPHABET = '0123456789BCDFGHJKLMNPQRSTVWXY'
	DESIGN_CODE_ALPHABET_VALUES = {c: val for val, c in enumerate(DESIGN_CODE_ALPHABET)}

	_design_code_segment = f'[{DESIGN_CODE_ALPHABET}]{{4}}'
	regex = re.compile('-'.join([_design_code_segment] * 3))
	del _design_code_segment

class UnknownAuthorIdError(DesignError):
	code = 203
	message = 'unknown author ID'
	http_status = HTTPStatus.NOT_FOUND

class InvalidScaleFactorError(InvalidFormatError):
	message = 'invalid scale factor'
	code = 204
	regex = re.compile('[123456]')

class InvalidAuthorIdError(DesignError, InvalidFormatError):
	code = 205
	message = 'invalid author ID'
	regex = re.compile('\d{4}-?\d{4}-?\d{4}', re.ASCII)

class InvalidProArgument(DesignError, InvalidFormatError):
	message = 'invalid value for pro argument'
	code = 206
	regex = re.compile('[01]|(?:false|true)|[ft]', re.IGNORECASE)

# not an invalid format error because it's not constrainable to a regex
class InvalidDesignError(DesignError):
	code = 207
	message = 'invalid design'
	http_status = HTTPStatus.BAD_REQUEST

class InvalidPaletteError(DesignError):
	code = 208
	message = f'the combined palette of all layers exceeds {PALETTE_SIZE} colors'
	http_status = HTTPStatus.BAD_REQUEST

class InvalidLayerSizeError(DesignError):
	code = 209
	message = 'layer "{0.layer.name}" did not meet the expected size ({0.layer.size[0]}×{0.layer.size[1]})'

class CannotScaleThumbnailError:
	message = 'cannot scale thumbnails'
	code = 230
	http_status = HTTPStatus.BAD_REQUEST

class UnknownImageIdError(ImageError):
	code = 301
	message = 'unknown image ID'
	http_status = HTTPStatus.NOT_FOUND

class InvalidLayerIndexError(ACNHError):
	code = 302
	message = 'invalid image layer'

	def __init__(self, *, num_layers):
		self.num_layers = num_layers

	def to_dict(self):
		d = super().to_dict()
		d['num_layers'] = self.num_layers

class DeletionDeniedError(ImageError):
	code = 303
	message = 'you do not own this image'
	http_status = HTTPStatus.UNAUTHORIZED

class InvalidImageError(ImageError):
	http_status = HTTPStatus.BAD_REQUEST

class SingleLayerRequired(InvalidImageError):
	code = 304
	message = (
		'A single layer was required, but more than one was passed. '
		'If tiling was requested, do not pass multiple layers.'
	)

class InvalidLayerSizeError(InvalidImageError):
	code = 305
	message = 'One or more layers was not {0.width}×{0.height}.'

	def __init__(self, width, height):
		super().__init__()
		self.width = width
		self.height = height

	def to_dict(self):
		d = super().to_dict()
		d['expected_width'] = self.width
		d['expected_height'] = self.height
		d['expected_byte_length'] = self.width * self.height * BYTES_PER_PIXEL
		d['message'] = self.message.format(self)
		return d

class TiledImageTooBigError(InvalidImageError):
	code = 306
	message = f'The uploaded image would exceed {MAX_DESIGN_TILES} tiles.'
	status = HTTPStatus.REQUEST_ENTITY_TOO_LARGE

	@classmethod
	def validate(cls, img):
		if num_tiles(img.width, img.height) > MAX_DESIGN_TILES:
			raise cls

class InvalidImageArgument(ImageError):
	code = 307
	message = 'missing or invalid required image argument {.argument_name}'
	http_status = HTTPStatus.BAD_REQUEST

	def __init__(self, argument_name):
		self.argument_name = argument_name

	def to_dict(self):
		d = super().to_dict()
		d['argument_name'] = self.argument_name
		d['error'] = d['error'].format(self)
		return d

class InvalidLayerNameError(DesignError):
	code = 308
	message = 'Invalid image layer name.'
	valid_layer_names: List[str]
	http_status = HTTPStatus.BAD_REQUEST

	def __init__(self, design):
		self.valid_layer_names = list(design.external_layer_names)

	def to_dict(self):
		d = super().to_dict()
		d['valid_layer_names'] = self.valid_layer_names
		return d

# TODO add which layer failed
class InvalidLayerError(DesignError):
	layer: 'Layer'
	http_status = HTTPStatus.BAD_REQUEST

	def __init__(self, layer):
		self.layer = layer

	def to_dict(self):
		d = super().to_dict()
		d['layer_name'] = self.layer.name
		d['layer_size'] = self.layer.size
		d['error'] = self.message.format(self)
		return d

class MissingLayerError(InvalidLayerError):
	code = 309
	message = 'Payload was missing one or more layers. First missing layer: "{0.layer.name}"'
	http_status = HTTPStatus.BAD_REQUEST

class InvalidImageError(ImageError):
	code = 310
	message = 'One or more layers submitted represented an invalid image.'
	status = HTTPStatus.BAD_REQUEST

class InvalidImageIdError(ImageError, InvalidFormatError):
	code = 311  # XXX rip my nice "x/10 = category" system
	message = 'Invalid image ID.'
	regex = re.compile('[0-9]+')

class InvalidImageDeletionToken(ImageError, InvalidFormatError):
	code = 312
	message = 'invalid image deletion token'
	regex = re.compile('[a-zA-Z0-9]+')

class AuthorizationError(ACNHError):
	pass

class MissingUserAgentStringError(AuthorizationError):
	code = 901
	message = 'User-Agent header required'
	http_status = HTTPStatus.BAD_REQUEST

class IncorrectAuthorizationError(AuthorizationError):
	code = 902
	message = 'invalid or incorrect Authorization header'
	http_status = HTTPStatus.UNAUTHORIZED

	def __init__(self, path=None):
		self.path = path
		super().__init__()
