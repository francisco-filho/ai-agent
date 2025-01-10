import re
import httpx
import logging
from openai import OpenAI
from pydantic import BaseModel
from typing import Any

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARN)

class Tool(BaseModel):
    name: str
    description: str

    def run(self):
        pass


class PythonCalculator(Tool):
    """
    calcular:
    Executa um cáculo e retorna um número usando Python e garante que números flutuantes são usados quando necessários.
    ex: calcular: 4 * 7 / 3
    """
    
    def __init__(self):
        super().__init__(
            name="calcular", 
            description="""
            Executa um cáculo e retorna um número usando Python e garante que números flutuantes são usados quando necessários.
            ex: calcular: 4 * 7 / 3
            """)


    def run(self, formula: str):
        return eval(formula)

    def __str__(self):
        return f"{self.name}\n{self.description}"

    def __call__(self, formula):
        return self.run(formula)

class WikipediaTool(Tool):
    """
    wikipedia:
    A wikipedia possui informações atuais sobre conhecimentos gerais. Retorna um sumário após pesquisar na Wikipedia.
    ex: wikipedia: Django
    """
    
    def __init__(self):
        super().__init__(
            name="wikipedia", 
            description="""
            A wikipedia possui informações atuais sobre conhecimentos gerais. Retorna um sumário após pesquisar na Wikipedia.
            ex: wikipedia: Django
            """)


    def run(self, q):
        response = httpx.get("https://pt.wikipedia.org/w/api.php", params={
            "action": "query",
            "list": "search",
            "srsearch": q,
            "format": "json"
        })
        return response.json()["query"]["search"][0]["snippet"]

    def __str__(self):
        return f"{self.name}\n{self.description}"

    def __call__(self, q):
        return self.run(q)

class Chatbot(BaseModel):
    system: str | None = None 
    messages: list[dict] = []


class ChatbotOpenAI(Chatbot):
    openai: Any = None

    def __init__(self, system=None):
        super().__init__(system=system)
        if system:
            self.messages.append({"role": "system", "content": self.system})
        self.openai = OpenAI()

    def __call__(self, message):
        self.messages.append({"role": "user", "content": message})
        result = self.execute()
        self.messages.append({"role": "assistant", "content": result})
        return result

    def execute(self):
        completion = self.openai.chat.completions.create(model="gpt-4o-mini", messages=self.messages)
        return completion.choices[0].message.content


prompt=f"""
Você funciona em um loop de Pensamento, Ação, PAUSA e Observaçao.
No final do loop você exibe a resposta.
Use Pensamento para descrever o que você acha que devem ser as ações a serem tomadas.
Use Ação para executar uma das ações disponíveis e então você PAUSA.
Observação será o resultado de executar uma Ação

Ações disponíveis:
{str(PythonCalculator())}
{str(WikipediaTool())}

chat:
Responde questão com informações já conhecidas pelo modelo.
ex: chat: Qual a capital do Brasil?

Exemplo de uma sessão:
Pergunta: Qual a capital da França?
Pensamento: Eu devo pesquisar conteudo sobre a França na Wikipedia.
Ação: wikipedia: França
PAUSA

Você será chamado novamente com isto:
Observação: França é um país. Sua captial é Paris.

Você então irá retornar:
Resposta: A capital da França é Paris. 
"""

action_re = re.compile(r"^Ação: (\w+): (.*)")

def chat(question):
    chat = ChatbotOpenAI(system="Você responde as questões da maneira mais suscinta possível, sem explicações")
    return chat(question)

acoes = {
    "calcular": PythonCalculator(),
    "wikipedia": WikipediaTool(),
    "chat": chat,
}

class Agente(BaseModel):
    name: str
    description: str = ""
    max_turns: int

    def __init__(self, name, max_turns=5):
        super().__init__(name=name, max_turns=max_turns)

    def run(self, task):
        print(task)

def query(question, max_turns=5):
    i = 0
    bot = ChatbotOpenAI(prompt)
    next_prompt = question
    print(f"Respondendo a questão: {question}")
    while i < max_turns:
        i += 1
        result = bot(next_prompt)
        logging.info(result)
        actions = [action_re.match(a) for a in result.split("\n") if action_re.match(a)]
        if actions:
            action, input = actions[0].groups()
            if action not in acoes:
                raise Exception(f"Ação não encontrada: {action} {input}")
            logging.info(f"Ação: {action}:{input} - Running")
            obs = acoes[action](input)
            logging.info(f"Observação: {obs}")
            next_prompt = f"Observação: {obs}"
        else:
            return result

if __name__ == '__main__':
    #chat = ChatbotOpenAI(system="você fala português nativo")
    #resp = query("Quem é a empresa produtora da série 'Arcane' da Netflix")

    question = input("Ask a question: ")
    resp = query(question)

