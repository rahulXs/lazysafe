"""fixture for testing framework registration decorators."""


class App:
    def route(self, path):
        def decorator(f):
            return f
        return decorator

    def component(self, name):
        def decorator(f):
            return f
        return decorator


app = App()


@app.route("/api")
@app.component("main")
def handler():
    pass
