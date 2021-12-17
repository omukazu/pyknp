# -*- encoding: utf-8 -*-

from __future__ import absolute_import
from __future__ import unicode_literals

import distutils.spawn
import os
import unittest
from collections import defaultdict as ddict

import six

from pyknp import BList
from pyknp import Juman, JUMAN_FORMAT
from pyknp.utils.analyzer import Analyzer


class KNP(object):
    """ KNPを用いて構文解析を行う/KNPの解析結果を読み取るモジュール

    Args:
        command (str): KNPコマンド
        option (str): KNP解析オプション
                        (詳細解析結果を出力する-tabは必須。
                        省略・照応解析を行う -anaphora, 格解析を行わず構文解析のみを行う -dpnd など)
        rcfile (str): KNP設定ファイルへのパス
        pattern (str): KNP出力の終端記号
        jumancommand (str): JUMANコマンド
        jumanrcfile (str): JUMAN設定ファイルへのパス
        jumanpp (bool): JUMAN++を用いるかJUMANを用いるか
        multithreading (bool): 解析をメインスレッド以外から行う可能性があるか
    """

    def __init__(self,
                 command='knp',
                 server=None,
                 port=31000,
                 timeout=60,
                 option='-tab',
                 rcfile='',
                 pattern=r'EOS',
                 jumancommand='jumanpp',
                 jumanrcfile='',
                 jumanoption='',
                 jumanpp=True,
                 multithreading=False,
                 ):
        self.command = command
        self.server = server
        self.port = port
        self.timeout = timeout
        self.options = option.split()
        self.rcfile = rcfile
        self.pattern = pattern
        if server is not None:
            self.analyzer = Analyzer(backend='socket', timeout=timeout, server=server, port=port,
                                     socket_option='RUN -tab -normal\n')
        else:
            cmds = [self.command] + self.options
            if self.rcfile:
                cmds += ['-r', self.rcfile]
            self.analyzer = Analyzer(backend='subprocess', multithreading=multithreading, timeout=timeout, command=cmds)
        self.jumanpp = jumanpp

        if self.rcfile and not os.path.isfile(os.path.expanduser(self.rcfile)):
            raise Exception("Can't read rcfile (%s)!" % self.rcfile)
        if distutils.spawn.find_executable(self.command) is None:
            raise Exception("Can't find KNP command: %s" % self.command)

        self.juman = Juman(command=jumancommand, rcfile=jumanrcfile, option=jumanoption, jumanpp=self.jumanpp,
                           multithreading=multithreading)

    def knp(self, sentence):
        """ parse関数と同じ """
        self.parse(sentence)

    def parse(self, sentence, juman_format=JUMAN_FORMAT.DEFAULT):
        """
        入力された文字列に対して形態素解析と構文解析を行い、文節列オブジェクトを返す

        Args:
            sentence (str): 文を表す文字列
            juman_format (JUMAN_FORMAT): Jumanのlattice出力形式

        Returns:
            BList: 文節列オブジェクト
        """
        assert isinstance(sentence, six.text_type)
        juman_lines = self.juman.juman_lines(sentence)
        juman_str = "%s%s" % (juman_lines, self.pattern)
        return self.parse_juman_result(juman_str, juman_format)

    @staticmethod
    def lattice2juman_line(values, the_same_mrph_id):
        features = [f'代表表記:{values[6]}']
        features += values[17].split('|')
        juman_values = [
            values[5],  # midasi
            values[7],  # yomi
            values[8],  # genkei
            values[9],  # hinsi
            values[10],  # hinsi_id
            values[11],  # bunrui
            values[12],  # bunrui_id
            values[13],  # katuyou
            values[14],  # katuyou_id
            values[15],  # katuyou2
            values[16],  # katuyou2_id
            f'"{" ".join(features)}"'
        ]
        juman_line = ' '.join(juman_values)
        if the_same_mrph_id:
            juman_line = '@ ' + juman_line
        return juman_line

    def lattice_all2juman_lines(self, lattice_all):
        juman_lines = ddict(list)

        comment, prev_id = '', '0'
        for line in lattice_all.split('\n'):
            if line.startswith('#'):
                comment = line
                continue
            elif line == 'EOS':
                continue
            values, ranks = line.split("\t"), line.split('|')[-1].split(':')[-1]

            the_same_mrph_id = (values[1] == prev_id)
            if not the_same_mrph_id:
                prev_id = values[1]

            for rank in ranks.split(';'):
                juman_lines[rank].append(self.lattice2juman_line(values, the_same_mrph_id))

        rank2juman_lines = {
            rank: '{0}\n{1}\nEOS'.format(comment, '\n'.join(lines)) for rank, lines in juman_lines.items()
        }
        juman_lines = [spec for rank, spec in sorted(rank2juman_lines.items())]
        return juman_lines

    def parse_juman_result(self, juman_str, juman_format=JUMAN_FORMAT.DEFAULT):
        """
        JUMAN出力結果に対して構文解析を行い、文節列オブジェクトを返す

        Args:
            juman_str (str): ある文に関するJUMANの出力結果
            juman_format (JUMAN_FORMAT): Jumanのlattice出力形式

        Returns:
            BList: 文節列オブジェクト
        """

        if juman_format == JUMAN_FORMAT.LATTICE_ALL:
            blists = []
            for juman_lines in self.lattice_all2juman_lines(juman_str):
                knp_lines = self.analyzer.query(juman_lines, pattern=r'^%s$' % self.pattern)
                blists.append(BList(f'{knp_lines}EOS\n', self.pattern, JUMAN_FORMAT.DEFAULT))
            return blists
        else:
            knp_lines = self.analyzer.query(juman_str, pattern=r'^%s$' % self.pattern)
            return BList(knp_lines, self.pattern, juman_format)

    def reparse_knp_result(self, knp_str, juman_format=JUMAN_FORMAT.DEFAULT):
        """
        KNP出力結果に対してもう一度構文解析を行い、文節列オブジェクトを返す。
        KNPのfeatureを再付与する場合などに用いる。中身はparse_juman_result関数と同じ。

        Args:
            knp_str (str): ある文に関するKNPの出力結果
            juman_format (JUMAN_FORMAT): Jumanのlattice出力形式

        Returns:
            BList: 文節列オブジェクト
        """
        return self.parse_juman_result(knp_str, juman_format=juman_format)

    def result(self, input_str, juman_format=JUMAN_FORMAT.DEFAULT):
        """
        ある文に関するKNP解析結果を文節列オブジェクトに変換する

        Args:
            input_str (str): ある文に関するKNPの出力結果
            juman_format (JUMAN_FORMAT): Jumanのlattice出力形式

        Returns:
            BList: 文節列オブジェクト
        """
        return BList(input_str, self.pattern, juman_format)


class KNPTest(unittest.TestCase):

    def setUp(self):
        self.knp = KNP()

    def test_dpnd(self):
        result = self.knp.parse("赤い花が咲いた。")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].parent.bnst_id, 1)
        self.assertEqual(len(result[1].children), 1)
        self.assertEqual(result[1].children[0].bnst_id, 0)
        self.assertEqual(result[1].parent.bnst_id, 2)
        self.assertEqual(result[2].parent, None)

    def test_mrph(self):
        result = self.knp.parse("赤い花が咲いた。")
        self.assertEqual(
            ''.join([mrph.midasi for mrph in result[0].mrph_list()]), '赤い')
        self.assertEqual(
            ''.join([mrph.midasi for mrph in result[1].mrph_list()]), '花が')
        self.assertEqual(
            ''.join([mrph.midasi for mrph in result[2].mrph_list()]), '咲いた。')

    def test_mrph2(self):
        result = self.knp.parse("エネルギーを素敵にENEOS")
        self.assertEqual(
            ''.join([mrph.midasi for mrph in result[0].mrph_list()]), 'エネルギーを')
        self.assertEqual(
            ''.join([mrph.midasi for mrph in result[1].mrph_list()]), '素敵に')
        self.assertEqual(
            ''.join([mrph.midasi for mrph in result[2].mrph_list()]), 'ENEOS')


if __name__ == '__main__':
    unittest.main()
