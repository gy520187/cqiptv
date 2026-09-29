# OpenWrt package for cqiptv (IPTV collector + Web manager)
#
# 放入 OpenWrt SDK 的 package/ 目录后执行:
#   ./scripts/feeds update -a   (或跳过)
#   make menuconfig -> Network -> IPTV -> cqiptv
#   make package/cqiptv/compile V=s
#
# 依赖说明:
#   - APScheduler / tzlocal 不在 OpenWrt 官方源中, 已随包捆绑到
#     /usr/share/cqiptv/vendor (启动脚本会设置 PYTHONPATH)
#   - 其余依赖均来自官方源

include $(TOPDIR)/rules.mk

PKG_NAME:=cqiptv
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

PKG_LICENSE:=GPL-2.0-only
PKG_MAINTAINER:=cqiptv

include $(INCLUDE_DIR)/package.mk

define Package/cqiptv
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=IPTV
  TITLE:=IPTV channel/EPG collector with web UI and scheduler
  URL:=https://github.com/gy520187/cqiptv
  DEPENDS:=+python3 \
	+python3-flask \
	+python3-requests \
	+python3-yaml \
	+python3-ruamel-yaml \
	+python3-cryptodome \
	+python3-pillow \
	+python3-pytz \
	+python3-six
endef

define Package/cqiptv/description
  CQIPTV is an IPTV channel/EPG collector for Chongqing Telecom IPTV.
  It includes a Flask web UI, scheduled collection and playlist/EPG output.
  Data files are stored under /etc/cqiptv (config.yaml, data, output, log).
endef

# 纯 Python 数据包，无需编译
define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
endef

define Package/cqiptv/install
	$(INSTALL_DIR) $(1)/usr/share/cqiptv
	$(CP) ./files/usr/share/cqiptv/* $(1)/usr/share/cqiptv/

	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/cqiptv $(1)/etc/init.d/cqiptv

	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_DATA) ./files/etc/config/cqiptv $(1)/etc/config/cqiptv

	# 运行时工作目录（config.yaml / data / output / log）
	$(INSTALL_DIR) $(1)/etc/cqiptv
endef

$(eval $(call BuildPackage,cqiptv))