import json
import sys

from jarvis.core.agent import JarvisAgent


def send(message):

    sys.stdout.write(
        json.dumps(message)
        + "\n"
    )

    sys.stdout.flush()


def main():

    agent = JarvisAgent()

    send({
        "type": "ready"
    })

    for line in sys.stdin:

        line = line.strip()

        if not line:
            continue

        try:

            request = json.loads(line)

            request_type = request.get(
                "type"
            )

            if request_type == "ask":

                text = request.get(
                    "text",
                    ""
                )

                if not text:
                    continue

                try:

                    response = agent.run(text)

                    send({
                        "type": "response",
                        "response": str(response),
                    })

                except Exception as exc:

                    send({
                        "type": "error",
                        "error": str(exc),
                    })

            elif request_type == "shutdown":

                break

        except Exception as exc:

            send({
                "type": "error",
                "error": str(exc),
            })


if __name__ == "__main__":
    main()