"""公司管理（客户/供应商）"""

import click
from ..platform_service_cli import get_backend, output


@click.group()
def company():
    """公司管理（客户/供应商）"""
    pass


# ── 客户子命令组 ────────────────────────────────────────────────────────

@click.group()
def customer():
    """客户管理"""
    pass


@customer.command(name="list")
@click.option("--company-name", help="公司名称")
@click.option("--salesman-id", help="业务员ID")
@click.option("--status", help="状态")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def customer_list(company_name, salesman_id, status, page, size):
    """获取客户列表"""
    backend = get_backend()
    params = {"page": page, "size": size}
    if company_name:
        params["companyName"] = company_name
    if salesman_id:
        params["salesmanId"] = salesman_id
    if status:
        params["status"] = status
    result = backend.get("/api/company/customer/list", params=params)
    output(result)


@customer.command(name="get")
@click.option("--id", required=True, help="公司ID")
def customer_get(id):
    """根据ID获取公司详情"""
    backend = get_backend()
    result = backend.get("/api/company/findById", params={"id": id})
    output(result)


@customer.command(name="create")
@click.option("--company-name", required=True, help="公司名称")
@click.option("--abbreviation", required=True, help="公司简称")
@click.option("--contact-name", required=True, help="联系人姓名")
@click.option("--contact-mobile", required=True, help="联系人手机")
@click.option("--credit-code", help="统一社会信用代码")
@click.option("--credit-limit", type=float, help="信用额度")
@click.option("--cars", help="适用车型")
@click.option("--invest-amount", type=float, help="投资金额")
@click.option("--investor", help="投资人")
@click.option("--province", help="省份")
@click.option("--city", help="城市")
@click.option("--county", help="区/县")
@click.option("--detail-address", help="详细地址")
@click.option("--settle-method", help="结算方式")
@click.option("--settle-date", help="结算日期")
@click.option("--payment-term-id", help="付款条件ID")
@click.option("--logistics-name", help="物流公司名称")
@click.option("--company-group-id", help="公司分组ID")
def customer_create(company_name, abbreviation, contact_name, contact_mobile, credit_code, credit_limit, cars, invest_amount, investor, province, city, county, detail_address, settle_method, settle_date, payment_term_id, logistics_name, company_group_id):
    """创建客户"""
    backend = get_backend()
    data = {
        "companyName": company_name,
        "abbreviation": abbreviation,
        "contactName": contact_name,
        "contactMobile": contact_mobile,
    }
    if credit_code:
        data["creditCode"] = credit_code
    if credit_limit is not None:
        data["creditLimit"] = credit_limit
    if cars:
        data["cars"] = cars
    if invest_amount is not None:
        data["investAmount"] = invest_amount
    if investor:
        data["investor"] = investor
    if province:
        data["province"] = province
    if city:
        data["city"] = city
    if county:
        data["county"] = county
    if detail_address:
        data["detailAddress"] = detail_address
    if settle_method:
        data["settleMethod"] = settle_method
    if settle_date:
        data["settleDate"] = settle_date
    if payment_term_id:
        data["paymentTermId"] = payment_term_id
    if logistics_name:
        data["logisticsName"] = logistics_name
    if company_group_id:
        data["companyGroupId"] = company_group_id
    result = backend.post("/api/company/customer/add", json=data)
    output(result)


# ── 供应商子命令组 ──────────────────────────────────────────────────────

@click.group()
def supplier():
    """供应商管理"""
    pass


@supplier.command(name="list")
@click.option("--company-name", help="公司名称")
@click.option("--status", help="状态")
@click.option("--page", default=1, type=int, help="页码")
@click.option("--size", default=15, type=int, help="每页条数")
def supplier_list(company_name, status, page, size):
    """获取供应商列表"""
    backend = get_backend()
    params = {"page": page, "size": size}
    if company_name:
        params["companyName"] = company_name
    if status:
        params["status"] = status
    result = backend.get("/api/company/supplier/list", params=params)
    output(result)


@supplier.command(name="get")
@click.option("--id", required=True, help="公司ID")
def supplier_get(id):
    """根据ID获取公司详情"""
    backend = get_backend()
    result = backend.get("/api/company/findById", params={"id": id})
    output(result)


@supplier.command(name="create")
@click.option("--company-name", required=True, help="公司名称")
@click.option("--abbreviation", required=True, help="公司简称")
@click.option("--contact-name", required=True, help="联系人姓名")
@click.option("--contact-mobile", required=True, help="联系人手机")
@click.option("--province", help="省份")
@click.option("--city", help="城市")
@click.option("--county", help="区/县")
@click.option("--detail-address", help="详细地址")
@click.option("--settle-method", help="结算方式")
@click.option("--settle-date", help="结算日期")
@click.option("--payment-term-id", help="付款条件ID")
@click.option("--company-group-id", help="公司分组ID")
def supplier_create(company_name, abbreviation, contact_name, contact_mobile, province, city, county, detail_address, settle_method, settle_date, payment_term_id, company_group_id):
    """创建供应商"""
    backend = get_backend()
    data = {
        "companyName": company_name,
        "abbreviation": abbreviation,
        "contactName": contact_name,
        "contactMobile": contact_mobile,
    }
    if province:
        data["province"] = province
    if city:
        data["city"] = city
    if county:
        data["county"] = county
    if detail_address:
        data["detailAddress"] = detail_address
    if settle_method:
        data["settleMethod"] = settle_method
    if settle_date:
        data["settleDate"] = settle_date
    if payment_term_id:
        data["paymentTermId"] = payment_term_id
    if company_group_id:
        data["companyGroupId"] = company_group_id
    result = backend.post("/api/company/supplier/add", json=data)
    output(result)


# ── 公司通用命令 ────────────────────────────────────────────────────────

@company.command(name="audit")
@click.option("--id", required=True, help="公司ID")
@click.option("--status", help="审核状态")
@click.option("--auditor-remark", help="审核备注")
def company_audit(id, status, auditor_remark):
    """审核公司"""
    backend = get_backend()
    data = {"id": id}
    if status:
        data["status"] = status
    if auditor_remark:
        data["auditorRemark"] = auditor_remark
    result = backend.post("/api/company/audit", json=data)
    output(result)


@company.command(name="lock")
@click.option("--id", required=True, help="公司ID")
def company_lock(id):
    """锁定公司"""
    backend = get_backend()
    result = backend.post("/api/company/lock", json={"id": id})
    output(result)


@company.command(name="unlock")
@click.option("--id", required=True, help="公司ID")
def company_unlock(id):
    """解锁公司"""
    backend = get_backend()
    result = backend.post("/api/company/unlock", json={"id": id})
    output(result)


@company.command(name="delete")
@click.option("--id", required=True, help="公司ID")
def company_delete(id):
    """删除公司"""
    backend = get_backend()
    result = backend.post("/api/company/delete", json={"id": id})
    output(result)


@company.command(name="update")
@click.option("--id", required=True, help="公司ID")
@click.option("--company-name", help="公司名称")
@click.option("--abbreviation", help="公司简称")
@click.option("--credit-code", help="统一社会信用代码")
@click.option("--credit-limit", type=float, help="信用额度")
@click.option("--contact-name", help="联系人姓名")
@click.option("--contact-mobile", help="联系人手机")
@click.option("--cars", help="适用车型")
@click.option("--invest-amount", type=float, help="投资金额")
@click.option("--investor", help="投资人")
@click.option("--province", help="省份")
@click.option("--city", help="城市")
@click.option("--county", help="区/县")
@click.option("--detail-address", help="详细地址")
@click.option("--settle-method", help="结算方式")
@click.option("--settle-date", help="结算日期")
@click.option("--payment-term-id", help="付款条件ID")
@click.option("--logistics-name", help="物流公司名称")
@click.option("--company-group-id", help="公司分组ID")
@click.option("--status", help="状态")
def company_update(id, company_name, abbreviation, credit_code, credit_limit, contact_name, contact_mobile, cars, invest_amount, investor, province, city, county, detail_address, settle_method, settle_date, payment_term_id, logistics_name, company_group_id, status):
    """更新公司信息"""
    backend = get_backend()
    data = {"id": id}
    if company_name:
        data["companyName"] = company_name
    if abbreviation:
        data["abbreviation"] = abbreviation
    if credit_code:
        data["creditCode"] = credit_code
    if credit_limit is not None:
        data["creditLimit"] = credit_limit
    if contact_name:
        data["contactName"] = contact_name
    if contact_mobile:
        data["contactMobile"] = contact_mobile
    if cars:
        data["cars"] = cars
    if invest_amount is not None:
        data["investAmount"] = invest_amount
    if investor:
        data["investor"] = investor
    if province:
        data["province"] = province
    if city:
        data["city"] = city
    if county:
        data["county"] = county
    if detail_address:
        data["detailAddress"] = detail_address
    if settle_method:
        data["settleMethod"] = settle_method
    if settle_date:
        data["settleDate"] = settle_date
    if payment_term_id:
        data["paymentTermId"] = payment_term_id
    if logistics_name:
        data["logisticsName"] = logistics_name
    if company_group_id:
        data["companyGroupId"] = company_group_id
    if status:
        data["status"] = status
    result = backend.post("/api/company/update", json=data)
    output(result)


@company.command(name="auth")
@click.option("--id", help="公司ID")
@click.option("--company-name", help="公司名称")
@click.option("--credit-code", help="统一社会信用代码")
@click.option("--province", help="省份")
@click.option("--city", help="城市")
@click.option("--county", help="区/县")
@click.option("--detail-address", help="详细地址")
def company_auth(id, company_name, credit_code, province, city, county, detail_address):
    """公司认证"""
    backend = get_backend()
    data = {}
    if id:
        data["id"] = id
    if company_name:
        data["companyName"] = company_name
    if credit_code:
        data["creditCode"] = credit_code
    if province:
        data["province"] = province
    if city:
        data["city"] = city
    if county:
        data["county"] = county
    if detail_address:
        data["detailAddress"] = detail_address
    result = backend.post("/api/company/auth", json=data)
    output(result)


@company.command(name="login-auth")
@click.option("--id", required=True, help="公司ID")
def company_login_auth(id):
    """登录认证"""
    backend = get_backend()
    result = backend.post("/api/company/loginAuth", json={"id": id})
    output(result)


@company.command(name="comment")
def company_comment():
    """获取公司备注"""
    backend = get_backend()
    result = backend.get("/api/company/comment")
    output(result)


# ── 注册子命令组到 company ──────────────────────────────────────────────

company.add_command(customer)
company.add_command(supplier)
