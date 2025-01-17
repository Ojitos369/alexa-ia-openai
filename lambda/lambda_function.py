import os
import openai
import logging
from dotenv import load_dotenv
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response
from ask_sdk_core.utils import is_request_type, is_intent_name

load_dotenv()
# Configurar logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Clave de OpenAI
OPEN_AI_API = os.getenv("OPEN_AI_API")
print("OPEN_AI_API", OPEN_AI_API)
openai.api_key = OPEN_AI_API

def obtener_respuesta_openai(messages: list, model="basico") -> str:
    """
    Llama a la API de OpenAI usando ChatCompletion con todo el historial de mensajes.
    """
    try:
        respuesta = openai.ChatCompletion.create(
            model="gpt-4o" if model == "avanzado" else "gpt-4o-mini",
            # model="asst_2IHKpjntcemAC95p7ZfbUgyl",
            messages=messages,
            max_tokens=1500,
            temperature=0.7
        )
        texto = respuesta.choices[0].message.content.strip()
        texto = " ".join(texto.split())
        if not texto:
            texto = "Lo siento, no tengo una respuesta para eso."
        return texto
    except Exception as e:
        logger.error(f"Error al comunicarse con OpenAI: {e}", exc_info=True)
        return "Lo siento, no puedo obtener una respuesta en este momento."

class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        # Inicia la sesión con un array vacío de mensajes si no existe
        session_attributes = handler_input.attributes_manager.session_attributes
        if "messages" not in session_attributes:
            session_attributes["messages"] = []

        speech_text = "Cuéntame."
        return (
            handler_input.response_builder
                .speak(speech_text)
                .ask("¿Qué te gustaría saber?")
                .response
        )

class OpenAIIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("OpenAIIntent")(handler_input)

    def handle(self, handler_input):
        try:
            slots = handler_input.request_envelope.request.intent.slots
            pregunta_usuario = slots["pregunta"].value if ("pregunta" in slots and slots["pregunta"].value) else None

            if not pregunta_usuario:
                logger.info("No se detectó el slot 'pregunta'.")
                # Mantener la sesión abierta con .ask()
                return (
                    handler_input.response_builder
                        .speak("No he entendido tu pregunta. ¿Podrías repetirla?")
                        .ask("¿Puedes repetir tu pregunta?")
                        .response
                )

            logger.info(f"Usuario preguntó: {pregunta_usuario}")

            # Cargar o inicializar el historial de la sesión
            session_attributes = handler_input.attributes_manager.session_attributes
            if "messages" not in session_attributes:
                session_attributes["messages"] = []

            model = "basico"
            if pregunta_usuario.startswith("avanzado"):
                model = "avanzado"
                pregunta_usuario = pregunta_usuario[8:]
            # Agregar el mensaje del usuario al historial
            session_attributes["messages"].append({"role": "user", "content": pregunta_usuario})

            # Obtener respuesta de OpenAI con todo el historial
            respuesta_openai = obtener_respuesta_openai(session_attributes["messages"], model)

            # Agregar el mensaje del asistente al historial
            session_attributes["messages"].append({"role": "assistant", "content": respuesta_openai})

            # Seguimos preguntando si tiene otra pregunta, sesión permanece abierta
            return (
                handler_input.response_builder
                    .speak(respuesta_openai)
                    .ask("¿Tienes alguna otra pregunta?")
                    .response
            )
        except Exception as e:
            logger.error(f"Error en OpenAIIntentHandler: {e}", exc_info=True)
            # Error genérico, manteniendo sesión abierta
            return (
                handler_input.response_builder
                    .speak("Hubo un problema procesando tu solicitud. Por favor, inténtalo de nuevo.")
                    .ask("¿Qué deseas preguntar?")
                    .response
            )

class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        speech_text = ("Puedo ayudarte respondiendo preguntas sobre muchos temas. "
                       "Simplemente di: 'qué sabes sobre X' o 'dime sobre X'.")
        # Mantener sesión abierta con .ask()
        return (
            handler_input.response_builder
                .speak(speech_text)
                .ask("¿En qué más puedo ayudarte?")
                .response
        )

class FallbackIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        speech_text = ("Lo siento, no estoy segura de lo que quieres decir. "
                       "Intenta preguntarme algo diferente.")
        # Mantener sesión abierta con .ask()
        return (
            handler_input.response_builder
                .speak(speech_text)
                .ask("¿En qué más puedo ayudarte?")
                .response
        )

class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (
            is_intent_name("AMAZON.CancelIntent")(handler_input) or
            is_intent_name("AMAZON.StopIntent")(handler_input)
        )

    def handle(self, handler_input):
        # Aquí sí cerramos la sesión al usar sólo .speak()
        return handler_input.response_builder.speak("Adiós").response

class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # Aquí no es necesario hacer nada
        return handler_input.response_builder.response

class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error(exception, exc_info=True)
        # Mantener sesión abierta con .ask() en caso de error genérico
        return (
            handler_input.response_builder
                .speak("Lo siento, ha ocurrido un error interno.")
                .ask("¿Puedes intentar nuevamente?")
                .response
        )

sb = SkillBuilder()
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(OpenAIIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())
sb.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = sb.lambda_handler()
