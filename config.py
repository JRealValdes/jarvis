from enums.core_enums import ModelEnum, IdentificationFailedProtocolEnum

DEFAULT_MODEL = ModelEnum.GPT_3_5
IDENTIFICATION_FAILED_PROTOCOL = IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE
DB_DEBUG_MODE = True
EXPOSE_API_WITH_CLOUDFLARED = True
JWT_ALGORITHM = "HS256"
JWT_EXP_DELTA_SECONDS = 3600  # 1 hora
