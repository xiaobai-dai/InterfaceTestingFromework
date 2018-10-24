#!/usr/bin/env python
#coding=utf-8

import time
import unittest
import HTMLTestRunner
from TestRequest import *
from TestData import *
from Func import *
from BeautifulReport import BeautifulReport

report_path = os.path.abspath('..') + '\\report'

class CaseVariable:
	pass

def test_generator(case_datas, isSetupOrCase='case'):
	def test(self):
		if type(case_datas) == list:
			for case_data in case_datas:
				case(case_data,self)
		else:
			case(case_datas,self)
	def case(case_data,cls):
		if isSetupOrCase == 'setup' or isSetupOrCase == 'teardown':
			if case_data['API Name'] == '' or case_data['Active'] == 'No':
				print('{}跳过执行'.format(isSetupOrCase))
				return test
		Data = GetData()
		yml_data = None
		if case_data['API Name'] != '':
			# 如果执行函数
			if '${' in  case_data['API Name']:
				check = extract_functions(case_data['API Name'], CaseVariable)
				cls.assertTrue(check)
				print('{}'.format(isSetupOrCase) + '\n')
				print('函数{}执行成功'.format(case_data['API Name']) + '\n')
				print('============================================================')
				return test
			# 根据API NAME找到yml数据
			yml_data = Data.get_yml_data(Data.change_api_name(case_data['API Name']))
			# 数据不为空
			cls.assertNotEqual(yml_data, {}, '未找到对应的yml文件数据：{}'.format(case_data['API Name']))
			# yml数据加到case_data中
			for key, value in yml_data.items():
				case_data[key] = value
			# 有Host信息则替换yml中的url对应的host
			host = str(case_data['Host']).strip()
			if host != '':
				new_host = Data.get_config_data('Host', host)
				setattr(CaseVariable, host, new_host)
				case_data['url'] = new_host + '/' + case_data['url'].split('/', 3)[-1]
			case_data['Correlation'] = parse_data(case_data['Correlation'])
			case_data['Check Point'] = Data.change_check_point(case_data['Check Point'])
			# 根据Request Headers和Request Data替换case_data中的数据
			for function in [case_data['Request Headers'], case_data['Request Data']]:
				function = parse_data(function)
				if function:
					for k, v in function.items():
						k = k.split('.') if '.' in k else [k]
						k = [parse_string_value(x) for x in k]
						# 执行函数
						if '${' in v:
							new_v = parse_string_value(extract_functions(v))
							cls.assertIsNotNone(new_v)
						# 寻找变量
						elif '$' in v:
							new_v = parse_string_value(getattr(CaseVariable, v.replace('$', ''), None))
							cls.assertIsNotNone(new_v, '未定义变量{}'.format(v))
						# 字符串
						else:
							new_v = v
						change_data(yml_data, new_v, k)
		# 如果没有API NAME信息失败
		cls.assertIsNotNone(yml_data,'没有读取到API NAME信息')
		method = case_data['method']
		url = case_data['url']
		headers = ''
		request_data = ''
		# get方法
		if str(method).lower() == 'get':
			headers = case_data['headers']
			resp = TestRequest.test_request(url, method, headers=headers)
		# post方法
		elif str(method).lower() == 'post':
			try:
				content_type = case_data['headers']['content-type']
			except KeyError:
				content_type = ''
			# json和data形式
			if 'multipart/form-data' not in content_type:
				request_data = json.dumps(case_data['json']) if 'json' in content_type else case_data['data']
				headers = case_data['headers']
				resp = TestRequest.test_request(url, method, headers, request_data)
			# 上传文件
			else:
				request_data = parse_data(case_data['Request Data'])
				headers = case_data['headers']
				resp = eval('TestRequest.multipart_form_data')(url, headers, request_data)
		# 其他方法，遇到再补充
		else:
			resp = [-1]
			print(method)
		# status code为200
		cls.assertEqual(resp[0], 200,'\nrequest: {}\nresponse: {}'.format(request_data, resp))
		get_summary(url=url, method=method, resp=resp, isSetupOrCase=isSetupOrCase, headers=headers,
		            request_data=request_data)
		check_point = case_data['Check Point']
		if check_point:
			for key, value in check_point.items():
				# 转换形式data1.data2 ==> [data1][data2]
				key = parse_string(key)
				if type(value) == str:
					# 值为字符串直接对比
					new_value = getattr(CaseVariable, value.replace('$', ''), None) if '$' in value else value
					cls.assertIsNotNone(new_value, '未定义变量{}'.format(value))
					cls.assertEqual(eval(str(resp[1]) + str(key)), new_value, '{}值不为{}'.format(key, new_value))
				elif type(value) == list:
					# 值为列表取对比方法
					# 目前支持=、in、not in
					new_value = getattr(CaseVariable, value[0].replace('$', ''), None) if '$' in value[0] else value[0]
					# 不为列表转换为字符串进行对比
					new_value = str(new_value) if type(new_value) != list else new_value
					assert_value = str(eval(str(resp[1]) + str(key))) if type(eval(str(resp[1]) + str(key))) != list else eval(str(resp[1]) + str(key))
					
					cls.assertIsNotNone(new_value, '未定义变量{}'.format(value))
					assertMethod = value[1]
					if assertMethod == '=':
						cls.assertTrue(assert_value == new_value,  '{}值不为{}'.format(key, new_value))
					elif str(assertMethod).lower() == 'in':
						if type(new_value) == list:
							cls.assertTrue(set(new_value) < set(assert_value), '{}值不在{}中'.format(new_value, key))
						else:
							cls.assertTrue(new_value in assert_value, '{}值不在{}中'.format(new_value, key))
					elif str(assertMethod).lower() == 'not in':
						if type(new_value) == list:
							cls.assertNotTrue(set(new_value) < set(assert_value), '{}值不在{}中'.format(new_value, key))
						else:
							cls.assertTrue(new_value not in eval(str(resp[1]) + str(key)),'{}值在{}中'.format(new_value, key))
					# 错误的断言方法
					else:
						print(check_point)
						cls.assertEqual('Check Point', '断言方法')
				# 错误的断言方法
				else:
					print(check_point)
					cls.assertEqual('Check Point', '断言方法')
		correlation = case_data['Correlation']
		# 取值，保存为类变量
		if correlation:
			for key, value in correlation.items():
				# 区分request和resp，分别取值
				if 'request.' in value:
					if 'json' in value:
						value = parse_string(value.replace('request.json.', ''))
						setattr(CaseVariable, key, eval(str(json.loads(request_data)) + str(value)))
					else:
						value = parse_string(value.replace('request.data.', ''))
						setattr(CaseVariable, key, eval(str(request_data) + str(value)))
				else:
					value = parse_string(value)
					setattr(CaseVariable, key, eval(str(resp[1]) + str(value)))
	return test

def get_summary(**kwargs):
	print('{}'.format(kwargs['isSetupOrCase']) + '\n')
	print('url: {}'.format(kwargs['url']) + '\n')
	print('method: {}'.format(kwargs['method']) + '\n')
	print('headers: {}'.format(kwargs['headers']) + '\n')
	print('request data: {}'.format(kwargs['request_data']) + '\n')
	print('status code: {}'.format(kwargs['resp'][0]) + '\n')
	print('response: {}'.format(kwargs['resp'][1]) + '\n')
	print('response time: {}'.format(kwargs['resp'][2]) + '\n')
	print('=========================================================================================================')
	
def get_sheetdata():
	all_caseinfo = GetData().get_case_data()
	for excel_datas in all_caseinfo:
		for sheet_datas in excel_datas:
			yield sheet_datas
		
def run_test():
	sheet_datas = get_sheetdata()
	loaded_testcases = []
	loader = unittest.TestLoader()
	username = GetData().get_config_data('Host', 'username')
	password = GetData().get_config_data('Host', 'password')
	setattr(CaseVariable, 'username', username)
	setattr(CaseVariable, 'password', password)
	for sheet_data in sheet_datas:
		sheet_name = sheet_data['sheet_name']
		TestSequense = type(sheet_name, (unittest.TestCase,), {})
		before_class = sheet_data['beforeClass']
		after_class = sheet_data['afterClass']
		setup_data = sheet_data['setup']
		teardown_data = sheet_data['teardown']
		case_datas = sheet_data['testcase']
		setup = test_generator(setup_data,'setup')
		teardown = test_generator(teardown_data, 'teardown')
		setattr(TestSequense, 'setUp', setup)
		setattr(TestSequense, 'tearDown', teardown)
		for n, case_data in enumerate(case_datas):
			test = test_generator(case_data)
			description = case_data['Description']
			setattr(TestSequense, 'test_{:03d}_{}'.format(n, description), test)
		loaded_testcase = loader.loadTestsFromTestCase(TestSequense)
		loaded_testcases.append(loaded_testcase)
	test_suite = unittest.TestSuite(loaded_testcases)
	now = time.strftime("%Y-%m-%d %H_%M_%S", time.localtime())
	# filename = report_path + '/' + now + "_result.html"
	filename = now + "_result.html"
	# fp = open(filename, 'wb')
	# runner = HTMLTestRunner.HTMLTestRunner(
	# 	stream=fp,
	# 	title=u'测试报告',
	# 	description=u'用例执行情况：')
	# runner.run(test_suite)
	
	# runner = unittest.TextTestRunner()
	# result = runner.run(test_suite)
	# print(result)
	
	result = BeautifulReport(test_suite)
	result.report(filename= filename, description ='接口测试', log_path =report_path)


if __name__ == "__main__":
	run_test()