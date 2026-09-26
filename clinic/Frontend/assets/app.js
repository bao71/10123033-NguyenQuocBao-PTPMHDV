(function () {
  "use strict";

  var app = angular.module("clinicApp", []);

  app.controller("ClinicController", [
    "$http",
    "$window",
    "$q",
    "$scope",
    function ($http, $window, $q, $scope) {
      var vm = this;
      var apiRoot = "/api/v1";
      var sessionKey = "clinic_session";
      var roleNames = {
        Admin: "Quản trị viên",
        Receptionist: "Lễ tân",
        Doctor: "Bác sĩ",
        Pharmacist: "Dược sĩ",
        Patient: "Bệnh nhân",
      };
      var modules = [
        {
          key: "users",
          title: "Tài khoản",
          icon: "◉",
          description: "Tạo nhân viên, tra cứu và khóa hoặc mở tài khoản.",
          permissions: ["users.read"],
          ready: true,
        },
        {
          key: "roles",
          title: "Phân quyền",
          icon: "▦",
          description: "Xem ma trận quyền và cấp quyền theo vai trò.",
          permissions: ["roles.read"],
          ready: true,
        },
        {
          key: "patients",
          title: "Hồ sơ bệnh nhân",
          icon: "♡",
          description: "Hồ sơ, tiền sử và kết quả cận lâm sàng.",
          permissions: [
            "patients.read",
            "patients.read_assigned",
            "patients.read_self",
          ],
          ready: false,
        },
        {
          key: "appointments",
          title: "Lịch hẹn",
          icon: "▤",
          description: "Đặt, tiếp nhận và theo dõi lịch khám.",
          permissions: [
            "appointments.read",
            "appointments.read_assigned",
            "appointments.read_self",
          ],
          ready: false,
        },
        {
          key: "encounters",
          title: "Khám bệnh",
          icon: "✚",
          description: "Chẩn đoán, bệnh án và kết luận khám.",
          permissions: ["encounters.read_assigned", "encounters.read_self"],
          ready: false,
        },
        {
          key: "prescriptions",
          title: "Đơn thuốc",
          icon: "◫",
          description: "Kê đơn và theo dõi đơn thuốc.",
          permissions: [
            "prescriptions.read_assigned",
            "prescriptions.read_self",
            "prescriptions.read_billing",
            "prescriptions.read_dispensing",
          ],
          ready: false,
        },
        {
          key: "inventory",
          title: "Nhà thuốc",
          icon: "▣",
          description: "Xuất thuốc và kiểm soát tồn kho.",
          permissions: ["inventory.read"],
          ready: false,
        },
        {
          key: "invoices",
          title: "Thu phí",
          icon: "▧",
          description: "Hóa đơn và thanh toán.",
          permissions: [
            "invoices.read",
            "invoices.read_assigned",
            "invoices.read_dispensing",
            "invoices.read_self",
          ],
          ready: false,
        },
        {
          key: "reports",
          title: "Báo cáo",
          icon: "▥",
          description: "Doanh thu theo bác sĩ.",
          permissions: ["reports.doctor_revenue_read"],
          ready: false,
        },
      ];

      vm.screen = "home";
      vm.authScreen = "login";
      vm.loginForm = {};
      vm.registerForm = {};
      vm.forgotForm = {};
      vm.resetForm = {};
      vm.staff = { role: "Receptionist" };
      vm.users = { items: [], page: 1, page_size: 20, total: 0 };
      vm.roles = { roles: [], available_permissions: [] };
      vm.selectedPermissions = {};
      vm.busy = false;

      function readSession() {
        try {
          return JSON.parse(
            $window.sessionStorage.getItem(sessionKey) || "null",
          );
        } catch (error) {
          return null;
        }
      }
      function saveSession(session) {
        $window.sessionStorage.setItem(sessionKey, JSON.stringify(session));
        vm.session = session;
        vm.user = session.user;
      }
      function clearSession() {
        $window.sessionStorage.removeItem(sessionKey);
        vm.session = null;
        vm.user = null;
        vm.screen = "home";
      }
      function errorMessage(error) {
        var body = error && error.data;
        if (body && body.error) {
          if (body.error.details && angular.isArray(body.error.details)) {
            return body.error.details
              .map(function (detail) {
                return detail.message;
              })
              .join(" ");
          }
          return body.error.message;
        }
        return "Không thể kết nối tới máy chủ. Vui lòng thử lại.";
      }
      function fail(error) {
        vm.error = errorMessage(error);
        vm.message = "";
      }
      vm.clearMessage = function () {
        vm.error = "";
        vm.message = "";
      };

      function refreshToken() {
        if (!vm.session || !vm.session.refresh_token) {
          return $q.reject();
        }
        return $http
          .post(apiRoot + "/auth/refresh", {
            refresh_token: vm.session.refresh_token,
          })
          .then(
            function (response) {
              saveSession(response.data);
              return response.data;
            },
            function (error) {
              clearSession();
              return $q.reject(error);
            },
          );
      }
      function api(method, path, data, config, retried) {
        var request = angular.extend(
          { method: method, url: apiRoot + path, data: data },
          config || {},
        );
        if (vm.session && vm.session.access_token) {
          request.headers = angular.extend({}, request.headers, {
            Authorization: "Bearer " + vm.session.access_token,
          });
        }
        return $http(request).catch(function (error) {
          if (
            error.status === 401 &&
            !retried &&
            vm.session &&
            path !== "/auth/refresh"
          ) {
            return refreshToken().then(function () {
              return api(method, path, data, config, true);
            });
          }
          return $q.reject(error);
        });
      }
      function run(work, onSuccess) {
        vm.clearMessage();
        vm.busy = true;
        return work()
          .then(function (response) {
            if (onSuccess) {
              onSuccess(response.data);
            }
          }, fail)
          .finally(function () {
            vm.busy = false;
          });
      }

      vm.roleName = function (role) {
        return roleNames[role] || role;
      };
      vm.can = function (permission) {
        return !!(
          vm.user &&
          vm.user.permissions &&
          vm.user.permissions.indexOf(permission) >= 0
        );
      };
      vm.visibleModules = function () {
        return modules.filter(function (item) {
          return item.permissions.some(vm.can);
        });
      };
      vm.screenTitle = function () {
        return vm.screen === "users"
          ? "Tài khoản"
          : vm.screen === "roles"
            ? "Phân quyền"
            : "Tổng quan";
      };
      vm.open = function (screen) {
        if (screen === "users" && !vm.can("users.read")) {
          return;
        }
        if (screen === "roles" && !vm.can("roles.read")) {
          return;
        }
        if (["home", "users", "roles"].indexOf(screen) < 0) {
          return;
        }
        vm.clearMessage();
        vm.screen = screen;
        if (screen === "users") {
          vm.loadUsers(1);
        }
        if (screen === "roles") {
          vm.loadRoles();
        }
      };
      vm.reloadMe = function (notify) {
        return api("GET", "/auth/me").then(function (response) {
          vm.user = response.data;
          vm.session.user = response.data;
          saveSession(vm.session);
          if (
            (vm.screen === "users" && !vm.can("users.read")) ||
            (vm.screen === "roles" && !vm.can("roles.read"))
          ) {
            vm.screen = "home";
          }
          if (notify) {
            vm.message = "Đã cập nhật quyền hiện tại.";
          }
        }, fail);
      };
      vm.login = function () {
        return run(
          function () {
            var body =
              "username=" +
              encodeURIComponent(vm.loginForm.username) +
              "&password=" +
              encodeURIComponent(vm.loginForm.password);
            return $http.post(apiRoot + "/auth/login", body, {
              headers: { "Content-Type": "application/x-www-form-urlencoded" },
            });
          },
          function (session) {
            saveSession(session);
            vm.loginForm.password = "";
            vm.screen = "home";
          },
        );
      };
      vm.register = function () {
        return run(
          function () {
            return $http.post(apiRoot + "/auth/register", vm.registerForm);
          },
          function (session) {
            saveSession(session);
            vm.registerForm = {};
            vm.screen = "home";
          },
        );
      };
      vm.forgot = function () {
        return run(
          function () {
            return $http.post(apiRoot + "/auth/forgot-password", vm.forgotForm);
          },
          function (data) {
            vm.message = data.message;
          },
        );
      };
      vm.reset = function () {
        return run(
          function () {
            return $http.post(apiRoot + "/auth/reset-password", vm.resetForm);
          },
          function (data) {
            vm.authScreen = "login";
            vm.resetForm = {};
            vm.message = data.message;
          },
        );
      };
      vm.logout = function () {
        var refresh = vm.session && vm.session.refresh_token;
        if (!refresh) {
          clearSession();
          return;
        }
        api("POST", "/auth/logout", {
          refresh_token: refresh,
          all_sessions: false,
        }).finally(function () {
          clearSession();
          vm.clearMessage();
        });
      };
      vm.loadUsers = function (page, keepMessage) {
        if (!vm.can("users.read")) {
          vm.screen = "home";
          return;
        }
        if (!keepMessage) {
          vm.clearMessage();
        }
        return api("GET", "/admin/users", null, {
          params: {
            page: page,
            page_size: 20,
            search: vm.userSearch || undefined,
          },
        }).then(function (response) {
          vm.users = response.data;
        }, fail);
      };
      vm.createStaff = function () {
        if (!vm.can("users.create")) {
          return;
        }
        var payload = angular.copy(vm.staff);
        if (payload.role !== "Doctor") {
          delete payload.doctor_code;
          delete payload.specialty;
          delete payload.license_number;
        }
        return run(
          function () {
            return api("POST", "/admin/users", payload);
          },
          function () {
            vm.staff = { role: "Receptionist" };
            vm.showCreate = false;
            vm.message = "Đã tạo tài khoản nhân viên.";
            vm.loadUsers(1, true);
          },
        );
      };
      vm.changeStatus = function (item, active) {
        var permission = active ? "users.update" : "users.deactivate";
        if (
          !vm.can(permission) ||
          (item.user_id === vm.user.user_id && !active)
        ) {
          return;
        }
        return run(
          function () {
            return api(
              "PATCH",
              "/admin/users/" + encodeURIComponent(item.user_id) + "/status",
              { is_active: active },
            );
          },
          function () {
            item.is_active = active;
            vm.message = active
              ? "Đã mở khóa tài khoản."
              : "Đã khóa tài khoản.";
          },
        );
      };
      vm.loadRoles = function () {
        if (!vm.can("roles.read")) {
          vm.screen = "home";
          return;
        }
        vm.clearMessage();
        return api("GET", "/admin/roles").then(function (response) {
          vm.roles = response.data;
          var chosen =
            vm.roles.roles.find(function (role) {
              return vm.selectedRole && role.code === vm.selectedRole.code;
            }) || vm.roles.roles[0];
          if (chosen) {
            vm.selectRole(chosen);
          }
        }, fail);
      };
      vm.selectRole = function (role) {
        vm.selectedRole = role;
        vm.selectedPermissions = {};
        role.permissions.forEach(function (permission) {
          vm.selectedPermissions[permission] = true;
        });
      };
      vm.selectedCount = function () {
        return Object.keys(vm.selectedPermissions).filter(function (code) {
          return vm.selectedPermissions[code];
        }).length;
      };
      vm.saveRole = function () {
        if (!vm.can("roles.update") || !vm.selectedRole) {
          return;
        }
        var permissions = Object.keys(vm.selectedPermissions).filter(
          function (code) {
            return vm.selectedPermissions[code];
          },
        );
        return run(
          function () {
            return api(
              "PUT",
              "/admin/roles/" +
                encodeURIComponent(vm.selectedRole.code) +
                "/permissions",
              { permissions: permissions },
            );
          },
          function (role) {
            vm.selectedRole.permissions = role.permissions;
            vm.message =
              "Đã lưu quyền cho vai trò " + vm.roleName(role.code) + ".";
            vm.reloadMe(false);
          },
        );
      };

      var initialSession = readSession();
      if (initialSession && initialSession.access_token) {
        saveSession(initialSession);
        vm.reloadMe(false);
      }
    var query = new URLSearchParams($window.location.search);
    var view = query.get("view");
    if (["register", "forgot", "reset"].indexOf(view) >= 0) {
      vm.authScreen = view;
    }
    var token = query.get("token");
      if (token && !vm.user) {
        vm.authScreen = "reset";
        vm.resetForm.token = token;
      }
      $scope.$on("$destroy", angular.noop);
    },
  ]);
})();
