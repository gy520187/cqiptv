# OpenWrt LuCI package for cqiptv
#
# 放入 OpenWrt SDK 的 package/ 目录后执行:
#   make menuconfig -> LuCI -> Applications -> luci-app-cqiptv
#   make package/luci-app-cqiptv/compile V=s

include $(TOPDIR)/rules.mk

PKG_NAME:=luci-app-cqiptv
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

PKG_LICENSE:=Apache-2.0
PKG_MAINTAINER:=cqiptv

include $(INCLUDE_DIR)/package.mk

define Package/luci-app-cqiptv
  SECTION:=luci
  CATEGORY:=LuCI
  SUBMENU:=3. Applications
  TITLE:=IPTV collector management (cqiptv)
  URL:=https://github.com/gy520187/cqiptv
  DEPENDS:=+cqiptv +luci-base
endef

define Package/luci-app-cqiptv/description
  LuCI JS view for cqiptv: view collection status, trigger collection,
  browse output files and tail runtime logs.
endef

# 纯前端资源，无需编译
define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Compile
endef

define Package/luci-app-cqiptv/install
	$(INSTALL_DIR) $(1)/usr/share/luci/menu.d
	$(INSTALL_DATA) ./files/usr/share/luci/menu.d/*.json $(1)/usr/share/luci/menu.d/

	$(INSTALL_DIR) $(1)/usr/share/rpcd/acl.d
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/*.json $(1)/usr/share/rpcd/acl.d/

	$(INSTALL_DIR) $(1)/www/luci-static/resources/view/cqiptv
	$(INSTALL_DATA) ./files/www/luci-static/resources/view/cqiptv/*.js $(1)/www/luci-static/resources/view/cqiptv/
endef

$(eval $(call BuildPackage,luci-app-cqiptv))