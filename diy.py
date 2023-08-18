import time
from datetime import datetime
import atexit
import json
import os

from arknights_mower.solvers.base_schedule import BaseSchedulerSolver
from arknights_mower.strategy import Solver
from arknights_mower.utils.device import Device
from arknights_mower.utils.email import task_template
from arknights_mower.utils.log import logger, init_fhlr
from arknights_mower.utils import config
from arknights_mower.utils.simulator import restart_simulator
# 下面不能删除
from arknights_mower.utils.operators import Operators, Operator, Dormitory
from arknights_mower.utils.scheduler_task import SchedulerTask

email_config= {
    # 发信账户
    'account':"xxx@qq.com",
    # 在QQ邮箱“帐户设置-账户-开启SMTP服务”中，按照指示开启服务获得授权码
    'pass_code':'xxx',
    # 收件人邮箱
    'receipts':['任何邮箱'],
    # 是否启用邮件提醒
    'mail_enable':False,
    # 邮件主题
    'subject': '任务数据'
}
maa_config = {
    "maa_enable":True,
    # 请设置为存放 dll 文件及资源的路径
    "maa_path":'F:\\MAA-v4.10.5-win-x64',
    # 请设置为存放 dll 文件及资源的路径
    "maa_adb_path":"D:\\Program Files\\Nox\\bin\\adb.exe",
    # adb 地址
    "maa_adb":['127.0.0.1:62001'],
    # maa 运行的时间间隔，以小时计
    "maa_execution_gap":4,
    # 以下配置，第一个设置为true的首先生效
    # 是否启动肉鸽
    "roguelike":False,
    # 是否启动生息演算
    "reclamation_algorithm":False,
    # 是否启动保全派驻
    "stationary_security_service": True,
    "sss_type": 2,
    "copilot_file_location": "F:\\MAA-v4.10.5-win-x64\\resource\\copilot\\SSS_雷神工业测试平台_浊蒂版.json",
    "copilot_loop_times":10,
    "last_execution": datetime.now(),
    "blacklist":"家具,碳,加急许可",
    "rogue_theme":"Sami",
    "buy_first":"招聘许可",
    "recruit_only_4": True,
    "credit_fight": False,
    "recruitment_time": None,
    'mall_ignore_when_full': True,
    "touch_option": "maatouch",
    "conn_preset": "General",
    "rogue": {
        "squad": "指挥分队",
        "roles": "取长补短",
        "use_support": False,
        "core_char":"",
        "use_nonfriend_support": False,
        "mode": 0,
        "investment_enabled": True,
        "stop_when_investment_full": False,
        "refresh_trader_with_dice": True
    },
    "sleep_min":"",
    "sleep_max":"",
    # "weekly_plan": [{"weekday": "周一", "stage": ['AP-5'], "medicine": 0},
    #                 {"weekday": "周二", "stage": ['PR-D-1'], "medicine": 0},
    #                 {"weekday": "周三", "stage": ['PR-C-2'], "medicine": 0},
    #                 {"weekday": "周四", "stage": ['AP-5'], "medicine": 0},
    #                 {"weekday": "周五", "stage": ['PR-A-2'], "medicine": 0},
    #                 {"weekday": "周六", "stage": ['AP-5'], "medicine": 0},
    #                 {"weekday": "周日", "stage": ['AP-5'], "medicine": 0}],
    "weekly_plan": [{"weekday": "周一", "stage": [''], "medicine": 0},
                    {"weekday": "周二", "stage": [''], "medicine": 0},
                    {"weekday": "周三", "stage": [''], "medicine": 0},
                    {"weekday": "周四", "stage": [''], "medicine": 0},
                    {"weekday": "周五", "stage": [''], "medicine": 0},
                    {"weekday": "周六", "stage": [''], "medicine": 0},
                    {"weekday": "周日", "stage": [''], "medicine": 0}]
}

# 模拟器相关设置
simulator= {
    "name":"夜神",
    # 多开编号，在模拟器助手最左侧的数字
    "index":2,
    # 用于执行模拟器命令
    "simulator_folder":"D:\\Program Files\\Nox\\bin"
}

# Free (宿舍填充)干员安排黑名单
free_blacklist= []

# 干员宿舍回复阈值
    # 高效组心情低于 UpperLimit  * 阈值 (向下取整)的时候才会会安排休息
    # UpperLimit：默认24，特殊技能干员如夕，令可能会有所不同(设置在 agent-base.json 文件可以自行更改)
resting_threshold = 0.5

# 跑单如果all in 贸易站则 不需要修改设置
# 如果需要无人机加速其他房间则可以修改成房间名字如 'room_1_1'
drone_room = None
# 无人机执行间隔时间 （小时）
drone_execution_gap = 4

reload_room = []

# 基地数据json文件保存名
state_file_name = 'state.json'

# 邮件时差调整
timezone_offset = 0

# 全自动基建排班计划：
# 这里定义了一套全自动基建的排班计划 plan_1
# agent 为常驻高效组的干员名

# group 为干员编队，你希望任何编队的人一起上下班则给他们编一样的名字
# replacement 为替换组干员备选
    # 暖机干员的自动换班
        # 目前只支持一个暖机干员休息
        # ！！ 会吧其他正在休息的暖机干员赶出宿舍
    # 请尽量安排多的替换干员，且尽量不同干员的替换人员不冲突
    # 龙舌兰和但书默认为插拔干员 必须放在 replacement的第一位
    # 请把你所安排的替换组 写入replacement 否则程序可能报错
    # 替换组会按照从左到右的优先级选择可以编排的干员
    # 宿舍常驻干员不会被替换所以不需要设置替换组
        # 宿舍空余位置请编写为Free，请至少安排一个群补和一个单补 以达到最大恢复效率
        # 宿管必须安排靠左，后面为填充干员
        # 宿舍恢复速率务必1-4从高到低排列
    # 如果有菲亚梅塔则需要安排replacement 建议干员至少为三
        # 菲亚梅塔会从replacment里找最低心情的进行充能
plan = {
    # 阶段 1
    "default": "plan_1",
    "plan_1": {
        # 中枢
        'central': [{'agent': '焰尾', 'group': '红松骑士', 'replacement': [ "阿米娅","凯尔希",]},
                    {'agent': '琴柳', 'group': '夕', 'replacement': [ "阿米娅","凯尔希","玛恩纳"]},
                    {'agent': '重岳', 'group': '', 'replacement': ["玛恩纳", "清道夫", "凯尔希", "阿米娅", '坚雷']},
                    {'agent': '夕', 'group': '夕', 'replacement': ["阿米娅","凯尔希","玛恩纳", "清道夫", "阿米娅", '坚雷']},
                    {'agent': '令', 'group': '', 'replacement': ["玛恩纳", "清道夫", "凯尔希", "阿米娅", '坚雷']},
                    ],
        'contact': [{'agent': '桑葚', 'group': '', 'replacement': ['艾雅法拉']}],
        # 宿舍
        'dormitory_1': [{'agent': '流明', 'group': '', 'replacement': []},
                        {'agent': '闪灵', 'group': '', 'replacement': []},
                        {'agent': 'Free', 'group': '', 'replacement': []},
                        {'agent': 'Free', 'group': '', 'replacement': []},
                        {'agent': 'Free', 'group': '', 'replacement': []}
                        ],
        'dormitory_2': [{'agent': '杜林', 'group': '', 'replacement': []},
                        {'agent': '蜜莓', 'group': '', 'replacement': []},
                        {'agent': '褐果', 'group': '', 'replacement': []},
                        {'agent': 'Free', 'group': '', 'replacement': []},
                        {'agent': 'Free', 'group': '', 'replacement': []}
                        ],
        'dormitory_3': [{'agent': '车尔尼', 'group': '', 'replacement': []},
                        {'agent': '斥罪', 'group': '', 'replacement': []},
                        {'agent': '爱丽丝', 'group': '', 'replacement': []},
                        {'agent': '桃金娘', 'group': '', 'replacement': []},
                        {'agent': 'Free', 'group': '', 'replacement': []}
                        ],
        'dormitory_4': [{'agent': '波登可', 'group': '', 'replacement': []},
                        {'agent': '夜莺', 'group': '', 'replacement': []},
                        {'agent': '菲亚梅塔', 'group': '', 'replacement': ['重岳', '令', '乌有']},
                        {'agent': 'Free', 'group': '', 'replacement': []},
                        {'agent': 'Free', 'group': '', 'replacement': []}],
        'factory': [{'agent': '年', 'replacement': ['九色鹿', '芳汀'], 'group': '夕'}],
        # 会客室
        'meeting': [{'agent': '伊内丝', 'replacement': ['陈', '红', '远山'], 'group': ''},
                    {'agent': '见行者', 'replacement': ['陈', '红', '星极'], 'group': ''}],
        'room_1_1': [{'agent': '乌有', 'group': '', 'replacement': ['伺夜']},
                     {'agent': '空弦', 'group': '图耶', 'replacement': ['龙舌兰', '鸿雪']},
                     {'agent': '伺夜', 'group': '图耶', 'replacement': ['但书','图耶']},
                     # {'agent': '伺夜', 'group': '图耶', 'replacement': ['但书','能天使']},
                     # {'agent': '空弦', '鸿雪': '图耶', 'replacement': ['龙舌兰', '雪雉']}
                     ],
        'room_1_2': [{'agent': '槐琥', 'group': '槐琥', 'replacement': ['贝娜']},
                     {'agent': '砾', 'group': '槐琥', 'Type': '', 'replacement': ['泡泡']},
                     {'agent': '至简', 'group': '槐琥', 'replacement': ['火神']}],
        'room_1_3': [{'agent': '承曦格雷伊', 'group': '异客', 'replacement': ['炎狱炎熔', '格雷伊']}],
        'room_2_2': [{'agent': '温蒂', 'group': '异客', 'replacement': ['火神']},
                     # {'agent': '异客', 'group': '异客', 'Type': '', 'replacement': ['贝娜']},
                     {'agent': '异客', 'group': '异客', 'Type': '', 'replacement': ['贝娜']},
                     {'agent': '森蚺', 'group': '异客', 'replacement': ['泡泡']}],
        'room_3_1': [{'agent': '稀音', 'group': '稀音', 'replacement': ['贝娜']},
                     {'agent': '帕拉斯', 'group': '稀音', 'Type': '', 'replacement': ['泡泡']},
                     {'agent': '红云', 'group': '稀音', 'replacement': ['火神']}],
        'room_2_3': [{'agent': '澄闪', 'group': '澄闪', 'replacement': ['炎狱炎熔', '格雷伊']}],
        'room_2_1': [{'agent': '食铁兽', 'group': '食铁兽', 'replacement': ['泡泡']},
                     {'agent': '断罪者', 'group': '食铁兽', 'replacement': ['火神']},
                     {'agent': '截云', 'group': '夕', 'replacement': ['迷迭香']}],
        'room_3_2': [{'agent': '灰毫', 'group': '红松骑士', 'replacement': ['贝娜']},
                     {'agent': '远牙', 'group': '红松骑士', 'Type': '', 'replacement': ['泡泡']},
                     {'agent': '野鬃', 'group': '红松骑士', 'replacement': ['火神']}],
        'room_3_3': [{'agent': '雷蛇', 'group': '澄闪', 'replacement': ['炎狱炎熔', '格雷伊']}]
    }
}

# UpperLimit、LowerLimit：心情上下限
# ExhaustRequire：是否强制工作到红脸再休息
# ArrangeOrder：指定在宿舍外寻找干员的方式
# RestInFull：是否强制休息到24心情再工作，与ExhaustRequire一起帮助暖机类技能工作更长时间
# RestingPriority：休息优先级，低优先级不会使用单回技能。

agent_base_config = {
    "Default": {"UpperLimit": 24, "LowerLimit": 0, "ExhaustRequire": False, "ArrangeOrder": [2, "false"],
                "RestInFull": False,"Workaholic":False},
    "令": {"LowerLimit": 12,"ArrangeOrder": [2, "true"]},
    "夕": {"UpperLimit": 12, "ArrangeOrder": [2, "true"]},
    "稀音": {"ExhaustRequire": True, "ArrangeOrder": [2, "true"], "RestInFull": True},
    "巫恋": {"ArrangeOrder": [2, "true"]},
    "柏喙": {"ExhaustRequire": True, "ArrangeOrder": [2, "true"]},
    "龙舌兰": {"ArrangeOrder": [2, "true"]},
    "空弦": {"ArrangeOrder": [2, "true"], "RestingPriority": "low"},
    "伺夜": {"ArrangeOrder": [2, "true"], "RestingPriority": "low"},
    "绮良": {"ArrangeOrder": [2, "true"]},
    "但书": {"ArrangeOrder": [2, "true"]},
    "泡泡": {"ArrangeOrder": [2, "true"]},
    "火神": {"ArrangeOrder": [2, "true"]},
    "黑键": {"ArrangeOrder": [2, "true"]},
    "波登可": {"ArrangeOrder": [2, "false"]},
    "夜莺": {"ArrangeOrder": [2, "false"]},
    "菲亚梅塔": {"ArrangeOrder": [2, "false"]},
    "流明": {"ArrangeOrder": [2, "false"]},
    "蜜莓": {"ArrangeOrder": [2, "false"]},
    "闪灵": {"ArrangeOrder": [2, "false"]},
    "杜林": {"ArrangeOrder": [2, "false"]},
    "褐果": {"ArrangeOrder": [2, "false"]},
    "车尔尼": {"ArrangeOrder": [2, "false"]},
    "安比尔": {"ArrangeOrder": [2, "false"]},
    "爱丽丝": {"ArrangeOrder": [2, "false"]},
    "桃金娘": {"ArrangeOrder": [2, "false"]},
    "帕拉斯": {"RestingPriority": "low"},
    "红云": {"RestingPriority": "low", "ArrangeOrder": [2, "true"]},
    "承曦格雷伊": {"ArrangeOrder": [2, "true"], "RestInFull": True},
    "乌有": {"ArrangeOrder": [2, "true"], "RestingPriority": "low"},
    "图耶": {"ArrangeOrder": [2, "true"]},
    "鸿雪": {"ArrangeOrder": [2, "true"]},
    "孑": {"ArrangeOrder": [2, "true"]},
    "清道夫": {"ArrangeOrder": [2, "true"]},
    "临光": {"ArrangeOrder": [2, "true"]},
    "杜宾": {"ArrangeOrder": [2, "true"]},
    "焰尾": {"RestInFull": True},
    "重岳": {"ArrangeOrder": [2, "true"]},
    "坚雷": {"ArrangeOrder": [2, "true"]},
    "年": {"RestingPriority": "low"},
    "伊内丝": {"ExhaustRequire": True, "ArrangeOrder": [2, "true"], "RestInFull": True},
    "铅踝":{"LowerLimit": 8,"UpperLimit": 12},
}


def debuglog():
    '''
    在屏幕上输出调试信息，方便调试和报错
    '''
    logger.handlers[0].setLevel('DEBUG')


def savelog():
    '''
    指定日志和截屏的保存位置，方便调试和报错
    调试信息和截图默认保存在代码所在的目录下
    '''
    config.LOGFILE_PATH = './log'
    config.SCREENSHOT_PATH = './screenshot'
    config.SCREENSHOT_MAXNUM = 30
    config.ADB_DEVICE = maa_config['maa_adb']
    config.ADB_CONNECT = maa_config['maa_adb']
    config.MAX_RETRYTIME = 10
    config.PASSWORD = '你的密码'
    config.APPNAME = 'com.hypergryph.arknights'  # 官服
    config.TAP_TO_LAUNCH["enable"] = False
    config.TAP_TO_LAUNCH["x"], config.TAP_TO_LAUNCH["y"] = 0,0
    #  com.hypergryph.arknights.bilibili   # Bilibili 服
    config.ADB_BINARY = ['F:\\MAA-v4.20.0-win-x64\\adb\\platform-tools\\adb.exe']
    init_fhlr()


def inialize(tasks, scheduler=None):
    device = Device()
    cli = Solver(device)
    if scheduler is None:
        base_scheduler = BaseSchedulerSolver(cli.device, cli.recog)
        base_scheduler.package_name = config.APPNAME
        base_scheduler.operators = {}
        base_scheduler.global_plan = plan
        base_scheduler.current_base = {}
        base_scheduler.resting = []
        base_scheduler.current_plan = base_scheduler.global_plan[base_scheduler.global_plan["default"]]
        # 同时休息最大人数
        base_scheduler.max_resting_count = 4
        base_scheduler.tasks = tasks
        # 读取心情开关，有菲亚梅塔或者希望全自动换班得设置为 true
        base_scheduler.read_mood = True
        base_scheduler.last_room = ''
        base_scheduler.free_blacklist = free_blacklist
        base_scheduler.resting_threshold = resting_threshold
        base_scheduler.MAA = None
        base_scheduler.email_config = email_config
        base_scheduler.ADB_CONNECT = config.ADB_CONNECT[0]
        base_scheduler.maa_config = maa_config
        base_scheduler.error = False
        base_scheduler.drone_count_limit = 92  # 无人机高于于该值时才使用
        base_scheduler.drone_room = drone_room
        base_scheduler.drone_execution_gap = drone_execution_gap
        base_scheduler.agent_base_config = agent_base_config
        base_scheduler.run_order_delay = 10  # 跑单提前10分钟运行
        base_scheduler.reload_room = reload_room
        return base_scheduler
    else:
        scheduler.device = cli.device
        scheduler.recog = cli.recog
        scheduler.handle_error(True)
        return scheduler

def save_state():
    with open(state_file_name, 'w') as f:
        if base_scheduler is not None and base_scheduler.op_data is not None:
            json.dump(vars(base_scheduler.op_data), f, default=str)

def load_state():
    if not os.path.exists(state_file_name):
        return None

    with open(state_file_name, 'r') as f:
        state = json.load(f)
    operators = {k: eval(v) for k, v in state['operators'].items()}
    for k, v in operators.items():
        if not v.time_stamp == 'None':
            v.time_stamp = datetime.strptime(v.time_stamp, '%Y-%m-%d %H:%M:%S.%f')
        else:
            v.time_stamp = None
    return operators


def simulate():
    '''
    具体调用方法可见各个函数的参数说明
    '''
    global ope_list, base_scheduler
    # 第一次执行任务
    taskstr = "SchedulerTask(time='2023-06-11 21:39:15.108665',task_plan={'room_3_2': ['Current', '但书', '龙舌兰']},task_type='room_3_2',meta_flag=False)||SchedulerTask(time='2023-06-11 21:44:48.187074',task_plan={'room_2_1': ['砾', '槐琥', '斑点']},task_type='dorm0,dorm1,dorm2',meta_flag=False)||SchedulerTask(time='2023-06-11 22:17:53.720905',task_plan={'room_1_1': ['Current', '龙舌兰', '但书']},task_type='room_1_1',meta_flag=False)||SchedulerTask(time='2023-06-11 23:02:10.469026',task_plan={'meeting': ['Current', '见行者']},task_type='dorm3',meta_flag=False)||SchedulerTask(time='2023-06-11 23:22:15.236154',task_plan={},task_type='菲亚梅塔',meta_flag=False)||SchedulerTask(time='2023-06-12 11:25:55.925731',task_plan={},task_type='impart',meta_flag=False)||SchedulerTask(time='2023-06-12 11:25:55.926731',task_plan={},task_type='maa_Mall',meta_flag=False)"
    tasks = [eval(t) for t in taskstr.split("||")]
    for t in tasks:
        t.time = datetime.strptime(t.time, '%Y-%m-%d %H:%M:%S.%f')
    reconnect_max_tries = 10
    reconnect_tries = 0
    success = False
    while not success:
        try:
            base_scheduler = inialize(tasks)
            success = True
        except Exception as E:
            reconnect_tries+=1
            if reconnect_tries <3:
                restart_simulator(simulator)
                continue
            else:
                raise E
    validation_msg = base_scheduler.initialize_operators()
    if validation_msg is not None:
        logger.error(validation_msg)
        return
    _loaded_operators = load_state()
    if _loaded_operators is not None:
        for k, v in _loaded_operators.items():
            if k in base_scheduler.op_data.operators and not base_scheduler.op_data.operators[k].room.startswith(
                    "dorm"):
                # 只复制心情数据
                base_scheduler.op_data.operators[k].mood = v.mood
                base_scheduler.op_data.operators[k].time_stamp = v.time_stamp
                base_scheduler.op_data.operators[k].depletion_rate = v.depletion_rate
                base_scheduler.op_data.operators[k].current_room = v.current_room
                base_scheduler.op_data.operators[k].current_index = v.current_index
    while True:
        try:
            if len(base_scheduler.tasks) > 0:
                (base_scheduler.tasks.sort(key=lambda x: x.time, reverse=False))
                sleep_time = (base_scheduler.tasks[0].time - datetime.now()).total_seconds()
                logger.info('||'.join([str(t) for t in base_scheduler.tasks]))
                base_scheduler.send_email(task_template.render(tasks=[obj.time_offset(timezone_offset) for obj in base_scheduler.tasks]), '', 'html')
                # 如果任务间隔时间超过9分钟则启动MAA
                if sleep_time > 540:
                    base_scheduler.maa_plan_solver()
                elif sleep_time > 0:
                    time.sleep(sleep_time)
            if len(base_scheduler.tasks) > 0 and base_scheduler.tasks[0].type.split('_')[0] == 'maa':
                base_scheduler.maa_plan_solver((base_scheduler.tasks[0].type.split('_')[1]).split(','), one_time=True)
                continue
            base_scheduler.run()
            reconnect_tries = 0
        except ConnectionError or ConnectionAbortedError as e:
            reconnect_tries += 1
            if reconnect_tries < reconnect_max_tries:
                logger.warning(f'连接端口断开....正在重连....')
                connected = False
                while not connected:
                    try:
                        base_scheduler = inialize([], base_scheduler)
                        break
                    except RuntimeError or ConnectionError or ConnectionAbortedError as ce:
                        logger.error(ce)
                        restart_simulator(simulator)
                        continue
                continue
            else:
                raise Exception(e)
        except RuntimeError as re:
            restart_simulator(simulator)
        except Exception as E:
            logger.exception(f"程序出错--->{E}")

    # cli.credit()  # 信用
    # ope_lists = cli.ope(eliminate=True, plan=ope_lists)  # 行动，返回未完成的作战计划
    # cli.shop(shop_priority)  # 商店
    # cli.recruit()  # 公招
    # cli.mission()  # 任务


# debuglog()
atexit.register(save_state)
savelog()
simulate()
