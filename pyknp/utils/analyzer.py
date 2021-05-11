from .process import Socket, Subprocess


class Analyzer(object):
    """サーバーやサブプロセスと通信して解析を行うクラス

    Args:
        backend (str): サーバーとサブプロセスのどちらで解析するか
        server (str): サーバーのホスト名
        port (int): サーバーのポート番号
        socket_option (str): ソケット通信の際のオプション
        command (list): サブプロセスに渡すコマンド
    """

    def __init__(self, backend, server=None, port=None, socket_option=None, command=None):
        self.backend = backend
        self.server = server
        self.port = port
        self.socket = None
        self.socket_option = socket_option

        self.subprocess = None
        self.command = command

    def query(self, input_str, pattern):
        if not self.socket and not self.subprocess:
            if self.server is not None:
                self.socket = Socket(self.server, self.port, self.socket_option)
            else:
                self.subprocess = Subprocess(self.command)

        if self.socket:
            return self.socket.query(input_str, pattern=pattern)
        else:
            return self.subprocess.query(input_str, pattern=pattern)