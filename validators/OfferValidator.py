class OfferValidator:
    
    @staticmethod
    def validate_device_offer(oferta: dict) -> bool:
        """
        Valida que un diccionario tenga la estructura correcta para una oferta de dispositivo.
        Lanza un ValueError o TypeError si algo falla.
        """
        # 1. Validar campos que deben ser Strings (Textos)
        string_fields = ["name", "origin", "type"]
        for field in string_fields:
            if field not in oferta:
                raise ValueError(f"Falta el campo obligatorio: '{field}'")
            if not isinstance(oferta[field], str):
                raise TypeError(f"El campo '{field}' debe ser un texto (string), pero es {type(oferta[field]).__name__}")

        # 2. Validar campos que deben ser Enteros (Números)
        int_fields = ["chat_id", "discount"]
        for field in int_fields:
            if field not in oferta:
                raise ValueError(f"Falta el campo numérico obligatorio: '{field}'")
            if not isinstance(oferta[field], int):
                raise TypeError(f"El campo '{field}' debe ser un número entero (int), pero es {type(oferta[field]).__name__}")

        # 3. Validación de negocio (Opcional pero recomendada)
        if oferta["type"] != "device":
            raise ValueError(f"El tipo de oferta no es válido para este método. Se recibió: {oferta['tipo']}")

        return True