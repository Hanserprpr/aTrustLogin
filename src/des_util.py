"""
DES / Triple-DES encryption ported from Des.java.
Used by SDU CAS login page to encrypt credentials and device fingerprints.
Keys are fixed to "1", "2", "3" as per the CAS login page's des.js.
"""

from __future__ import annotations
from typing import List

S1 = [
    [14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7],
    [0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8],
    [4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0],
    [15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13],
]

S2 = [
    [15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10],
    [3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5],
    [0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15],
    [13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9],
]

S3 = [
    [10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8],
    [13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1],
    [13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7],
    [1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12],
]

S4 = [
    [7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15],
    [13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9],
    [10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4],
    [3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14],
]

S5 = [
    [2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9],
    [14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6],
    [4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14],
    [11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3],
]

S6 = [
    [12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11],
    [10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8],
    [9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6],
    [4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13],
]

S7 = [
    [4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1],
    [13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6],
    [1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2],
    [6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12],
]

S8 = [
    [13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7],
    [1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2],
    [7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8],
    [2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11],
]

S_BOXES = [S1, S2, S3, S4, S5, S6, S7, S8]

BIN_4BIT = [
    "0000", "0001", "0010", "0011", "0100", "0101", "0110", "0111",
    "1000", "1001", "1010", "1011", "1100", "1101", "1110", "1111",
]
HEX_4BIT = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "A", "B", "C", "D", "E", "F"]


def _hex_char_to_int(c: str) -> int:
    if "0" <= c <= "9":
        return ord(c) - 48
    if "A" <= c <= "F":
        return ord(c) - 55
    if "a" <= c <= "f":
        return ord(c) - 87
    return 0


def _str_to_bt(s: str) -> List[int]:
    bt = [0] * 64
    length = len(s)
    for i in range(4):
        ch = ord(s[i]) if i < length else 0
        for j in range(16):
            bt[i * 16 + j] = (ch >> (15 - j)) & 1
    return bt


def _get_key_bytes(key: str) -> List[List[int]]:
    key_bytes: List[List[int]] = []
    length = len(key)
    iterator = length // 4
    remainder = length % 4
    for i in range(iterator):
        key_bytes.append(_str_to_bt(key[i * 4: i * 4 + 4]))
    if remainder > 0:
        key_bytes.append(_str_to_bt(key[iterator * 4:]))
    return key_bytes


def _build_key_list(first_key: str, second_key: str, third_key: str) -> List[List[int]]:
    keys: List[List[int]] = []
    if first_key:
        keys.extend(_get_key_bytes(first_key))
    if second_key:
        keys.extend(_get_key_bytes(second_key))
    if third_key:
        keys.extend(_get_key_bytes(third_key))
    return keys


def _init_permute(original_data: List[int]) -> List[int]:
    ip_byte = [0] * 64
    for i in range(4):
        m = i * 2 + 1
        n = i * 2
        for j in range(7, -1, -1):
            k = 7 - j
            ip_byte[i * 8 + k] = original_data[j * 8 + m]
            ip_byte[i * 8 + k + 32] = original_data[j * 8 + n]
    return ip_byte


def _expand_permute(right_data: List[int]) -> List[int]:
    ep_byte = [0] * 48
    for i in range(8):
        ep_byte[i * 6] = right_data[31] if i == 0 else right_data[i * 4 - 1]
        ep_byte[i * 6 + 1] = right_data[i * 4]
        ep_byte[i * 6 + 2] = right_data[i * 4 + 1]
        ep_byte[i * 6 + 3] = right_data[i * 4 + 2]
        ep_byte[i * 6 + 4] = right_data[i * 4 + 3]
        ep_byte[i * 6 + 5] = right_data[0] if i == 7 else right_data[i * 4 + 4]
    return ep_byte


def _xor(a: List[int], b: List[int]) -> List[int]:
    return [a[i] ^ b[i] for i in range(len(a))]


def _s_box_permute(expand_byte: List[int]) -> List[int]:
    s_box_byte = [0] * 32
    for m in range(8):
        i = (expand_byte[m * 6] << 1) | expand_byte[m * 6 + 5]
        j = (expand_byte[m * 6 + 1] << 3) | (expand_byte[m * 6 + 2] << 2) | (expand_byte[m * 6 + 3] << 1) | expand_byte[m * 6 + 4]
        value = S_BOXES[m][i][j]
        bin_str = BIN_4BIT[value]
        s_box_byte[m * 4] = ord(bin_str[0]) - 48
        s_box_byte[m * 4 + 1] = ord(bin_str[1]) - 48
        s_box_byte[m * 4 + 2] = ord(bin_str[2]) - 48
        s_box_byte[m * 4 + 3] = ord(bin_str[3]) - 48
    return s_box_byte


def _p_permute(s_box_byte: List[int]) -> List[int]:
    p = [0] * 32
    p[0] = s_box_byte[15]; p[1] = s_box_byte[6]; p[2] = s_box_byte[19]; p[3] = s_box_byte[20]
    p[4] = s_box_byte[28]; p[5] = s_box_byte[11]; p[6] = s_box_byte[27]; p[7] = s_box_byte[16]
    p[8] = s_box_byte[0]; p[9] = s_box_byte[14]; p[10] = s_box_byte[22]; p[11] = s_box_byte[25]
    p[12] = s_box_byte[4]; p[13] = s_box_byte[17]; p[14] = s_box_byte[30]; p[15] = s_box_byte[9]
    p[16] = s_box_byte[1]; p[17] = s_box_byte[7]; p[18] = s_box_byte[23]; p[19] = s_box_byte[13]
    p[20] = s_box_byte[31]; p[21] = s_box_byte[26]; p[22] = s_box_byte[2]; p[23] = s_box_byte[8]
    p[24] = s_box_byte[18]; p[25] = s_box_byte[12]; p[26] = s_box_byte[29]; p[27] = s_box_byte[5]
    p[28] = s_box_byte[21]; p[29] = s_box_byte[10]; p[30] = s_box_byte[3]; p[31] = s_box_byte[24]
    return p


def _finally_permute(end_byte: List[int]) -> List[int]:
    fp = [0] * 64
    fp[0] = end_byte[39]; fp[1] = end_byte[7]; fp[2] = end_byte[47]; fp[3] = end_byte[15]
    fp[4] = end_byte[55]; fp[5] = end_byte[23]; fp[6] = end_byte[63]; fp[7] = end_byte[31]
    fp[8] = end_byte[38]; fp[9] = end_byte[6]; fp[10] = end_byte[46]; fp[11] = end_byte[14]
    fp[12] = end_byte[54]; fp[13] = end_byte[22]; fp[14] = end_byte[62]; fp[15] = end_byte[30]
    fp[16] = end_byte[37]; fp[17] = end_byte[5]; fp[18] = end_byte[45]; fp[19] = end_byte[13]
    fp[20] = end_byte[53]; fp[21] = end_byte[21]; fp[22] = end_byte[61]; fp[23] = end_byte[29]
    fp[24] = end_byte[36]; fp[25] = end_byte[4]; fp[26] = end_byte[44]; fp[27] = end_byte[12]
    fp[28] = end_byte[52]; fp[29] = end_byte[20]; fp[30] = end_byte[60]; fp[31] = end_byte[28]
    fp[32] = end_byte[35]; fp[33] = end_byte[3]; fp[34] = end_byte[43]; fp[35] = end_byte[11]
    fp[36] = end_byte[51]; fp[37] = end_byte[19]; fp[38] = end_byte[59]; fp[39] = end_byte[27]
    fp[40] = end_byte[34]; fp[41] = end_byte[2]; fp[42] = end_byte[42]; fp[43] = end_byte[10]
    fp[44] = end_byte[50]; fp[45] = end_byte[18]; fp[46] = end_byte[58]; fp[47] = end_byte[26]
    fp[48] = end_byte[33]; fp[49] = end_byte[1]; fp[50] = end_byte[41]; fp[51] = end_byte[9]
    fp[52] = end_byte[49]; fp[53] = end_byte[17]; fp[54] = end_byte[57]; fp[55] = end_byte[25]
    fp[56] = end_byte[32]; fp[57] = end_byte[0]; fp[58] = end_byte[40]; fp[59] = end_byte[8]
    fp[60] = end_byte[48]; fp[61] = end_byte[16]; fp[62] = end_byte[56]; fp[63] = end_byte[24]
    return fp


def _generate_keys(key_byte: List[int]) -> List[List[int]]:
    key = [0] * 56
    for i in range(7):
        for j in range(8):
            k = 7 - j
            key[i * 8 + j] = key_byte[8 * k + i]

    loop = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1]
    keys: List[List[int]] = []

    for i in range(16):
        for _ in range(loop[i]):
            temp_left = key[0]
            temp_right = key[28]
            for k in range(1, 28):
                key[k - 1] = key[k]
            for k in range(29, 56):
                key[k - 1] = key[k]
            key[27] = temp_left
            key[55] = temp_right

        temp_key = [0] * 48
        temp_key[0] = key[13]; temp_key[1] = key[16]; temp_key[2] = key[10]; temp_key[3] = key[23]
        temp_key[4] = key[0]; temp_key[5] = key[4]; temp_key[6] = key[2]; temp_key[7] = key[27]
        temp_key[8] = key[14]; temp_key[9] = key[5]; temp_key[10] = key[20]; temp_key[11] = key[9]
        temp_key[12] = key[22]; temp_key[13] = key[18]; temp_key[14] = key[11]; temp_key[15] = key[3]
        temp_key[16] = key[25]; temp_key[17] = key[7]; temp_key[18] = key[15]; temp_key[19] = key[6]
        temp_key[20] = key[26]; temp_key[21] = key[19]; temp_key[22] = key[12]; temp_key[23] = key[1]
        temp_key[24] = key[40]; temp_key[25] = key[51]; temp_key[26] = key[30]; temp_key[27] = key[36]
        temp_key[28] = key[46]; temp_key[29] = key[54]; temp_key[30] = key[29]; temp_key[31] = key[39]
        temp_key[32] = key[50]; temp_key[33] = key[44]; temp_key[34] = key[32]; temp_key[35] = key[47]
        temp_key[36] = key[43]; temp_key[37] = key[48]; temp_key[38] = key[38]; temp_key[39] = key[55]
        temp_key[40] = key[33]; temp_key[41] = key[52]; temp_key[42] = key[45]; temp_key[43] = key[41]
        temp_key[44] = key[49]; temp_key[45] = key[35]; temp_key[46] = key[28]; temp_key[47] = key[31]
        keys.append(temp_key)

    return keys


def _enc(data_byte: List[int], key_byte: List[int]) -> List[int]:
    keys = _generate_keys(key_byte)
    ip_byte = _init_permute(data_byte)
    ip_left = ip_byte[:32]
    ip_right = ip_byte[32:]

    for i in range(16):
        temp_left = ip_left[:]
        ip_left = ip_right[:]
        temp_right = _xor(_p_permute(_s_box_permute(_xor(_expand_permute(ip_right), keys[i]))), temp_left)
        ip_right = temp_right

    final_data = ip_right + ip_left
    return _finally_permute(final_data)


def _bt64_to_hex(byte_data: List[int]) -> str:
    hex_str = ""
    for i in range(16):
        idx = (byte_data[i * 4] << 3) | (byte_data[i * 4 + 1] << 2) | (byte_data[i * 4 + 2] << 1) | byte_data[i * 4 + 3]
        hex_str += HEX_4BIT[idx]
    return hex_str


def str_enc(data: str, first_key: str = "1", second_key: str = "2", third_key: str = "3") -> str:
    if not data:
        return ""
    combined_keys = _build_key_list(first_key, second_key, third_key)
    if not combined_keys:
        return ""

    enc_data = ""
    length = len(data)
    iterator = length // 4
    remainder = length % 4

    for i in range(iterator):
        temp_data = data[i * 4: i * 4 + 4]
        temp_byte = _str_to_bt(temp_data)
        for k in combined_keys:
            temp_byte = _enc(temp_byte, k)
        enc_data += _bt64_to_hex(temp_byte)

    if remainder > 0:
        remainder_data = data[iterator * 4:]
        temp_byte = _str_to_bt(remainder_data)
        for k in combined_keys:
            temp_byte = _enc(temp_byte, k)
        enc_data += _bt64_to_hex(temp_byte)

    return enc_data
