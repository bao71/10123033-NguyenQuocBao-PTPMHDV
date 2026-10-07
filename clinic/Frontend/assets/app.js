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
          key: "reception", title: "Tiếp nhận", icon: "▤",
          description: "Lịch trong ngày, xác nhận, check-in và vắng hẹn.",
          permissions: ["appointments.check_in"], ready: true,
        },
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
          title: "Bệnh nhân",
          icon: "♡",
          description: "Thông tin hành chính và danh sách bệnh nhân.",
          permissions: [
            "patients.read",
            "patients.read_assigned",
            "patients.read_self",
          ],
          ready: true,
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
          ready: true,
        },
        {
          key: "encounters",
          title: "Khám bệnh",
          icon: "✚",
          description: "Chẩn đoán, bệnh án và kết luận khám.",
          permissions: ["encounters.read_assigned", "encounters.read_self"],
          ready: true,
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
      vm.patients = { items: [], page: 1, page_size: 20, total: 0 };
      vm.patientFilters = { sort_by: "created_at", sort_order: "desc", has_account: "" };
      vm.patientForm = {};
      vm.selectedPatient = null;
      vm.showPatientForm = false;
      vm.medicalHistories = { items: [], page: 1, page_size: 10, total: 0 };
      vm.historyFilters = {
        type: "", is_active: "", search: "", sort_by: "created_at", sort_order: "desc",
      };
      vm.historyForm = {};
      vm.showHistoryForm = false;
      vm.appointments = { items: [], page: 1, page_size: 20, total: 0 };
      vm.appointmentFilters = { status: "", sort_by: "appointment_at", sort_order: "asc" };
      vm.reception = { items: [], page: 1, page_size: 20, total: 0, summary: {} };
      vm.receptionFilters = { work_date: clinicDate(Date.now()), status: "", sort_order: "asc" };
      vm.receptionLoading = false;
      vm.encounters = { items: [], page: 1, page_size: 20, total: 0 };
      vm.encounterFilters = { status: "", sort_by: "started_at", sort_order: "desc" };
      vm.clinicalQueue = { items: [], page: 1, page_size: 20, total: 0 };
      vm.selectedEncounter = null;
      vm.encounterForm = {};
      vm.encounterHistories = [];
      vm.encounterVersions = { items: [], page: 1, page_size: 10, total: 0 };
      vm.showEncounterVersions = false;
      vm.orderForm = null;
      vm.resultForm = null;
      var encounterDetailRequest = 0;
      var encounterFormBaseline = {};
      var receptionRequestVersion = 0;
      vm.doctors = [];
      vm.bookingPatients = [];
      vm.appointmentForm = {};
      vm.scheduleForm = { slot_minutes: 30 };
      vm.schedules = { items: [], page: 1, page_size: 20, total: 0 };
      vm.slots = [];
      vm.showAppointmentForm = false;
      vm.showScheduleForm = false;
      vm.showSchedules = false;
      vm.slotsLoading = false;
      var slotRequestVersion = 0;
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
        vm.patients = { items: [], page: 1, page_size: 20, total: 0 };
        vm.selectedPatient = null;
        vm.patientForm = {};
        vm.showPatientForm = false;
        vm.medicalHistories = { items: [], page: 1, page_size: 10, total: 0 };
        vm.historyForm = {};
        vm.showHistoryForm = false;
        vm.appointments = { items: [], page: 1, page_size: 20, total: 0 };
        vm.reception = { items: [], page: 1, page_size: 20, total: 0, summary: {} };
        vm.receptionFilters = { work_date: clinicDate(Date.now()), status: "", sort_order: "asc" };
        vm.receptionLoading = false;
        vm.encounters = { items: [], page: 1, page_size: 20, total: 0 };
        vm.encounterFilters = { status: "", sort_by: "started_at", sort_order: "desc" };
        vm.clinicalQueue = { items: [], page: 1, page_size: 20, total: 0 };
        vm.selectedEncounter = null;
        vm.encounterForm = {};
        vm.encounterHistories = [];
        vm.orderForm = null;
        vm.resultForm = null;
        vm.showEncounterVersions = false;
        vm.encounterVersions = { items: [], page: 1, page_size: 10, total: 0 };
        encounterDetailRequest += 1;
        encounterFormBaseline = {};
        receptionRequestVersion += 1;
        vm.doctors = [];
        vm.bookingPatients = [];
        vm.appointmentForm = {};
        vm.slots = [];
        vm.showAppointmentForm = false;
        vm.showScheduleForm = false;
        vm.showSchedules = false;
        vm.cancelAppointmentForm = null;
        vm.schedules = { items: [], page: 1, page_size: 20, total: 0 };
        vm.scheduleForm = { slot_minutes: 30 };
        vm.slotsLoading = false;
        vm.appointmentFilters = { status: "", sort_by: "appointment_at", sort_order: "asc" };
        vm.doctorSearch = "";
        vm.bookingPatientSearch = "";
        vm.scheduleDoctorFilter = "";
        vm.scheduleDateFilter = "";
        slotRequestVersion += 1;
      }
      function errorMessage(error) {
        var body = error && error.data;
        if (body && body.error) {
          if (!vm.user) {
            var authMessages = {
              AUTHENTICATION_FAILED: "Incorrect username, email, or password.",
              ACCOUNT_ALREADY_EXISTS: "This account information is already in use.",
              INVALID_RESET_TOKEN: "This reset code is invalid or has expired.",
              RATE_LIMITED: "Too many attempts. Please try again later.",
              VALIDATION_ERROR: "Please check the information you entered.",
            };
            return authMessages[body.error.code] || "We couldn't complete your request. Please try again.";
          }
          if (body.error.details && angular.isArray(body.error.details)) {
            return body.error.details
              .map(function (detail) {
                return detail.message;
              })
              .join(" ");
          }
          return body.error.message;
        }
        return vm.user
          ? "Không thể kết nối tới máy chủ. Vui lòng thử lại."
          : "Cannot connect to the server. Please try again.";
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
      vm.genderName = function (gender) {
        return { male: "Nam", female: "Nữ", other: "Khác", unknown: "Chưa rõ" }[gender]
          || "Chưa cập nhật";
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
            : vm.screen === "patients"
              ? "Bệnh nhân"
            : vm.screen === "appointments"
              ? "Lịch hẹn"
            : vm.screen === "reception"
              ? "Tiếp nhận"
            : vm.screen === "encounters"
              ? (vm.can("encounters.read_assigned") ? "Khám bệnh" : "Bệnh án của tôi")
            : "Tổng quan";
      };
      vm.canReadPatients = function () {
        return vm.can("patients.read") ||
          vm.can("patients.read_assigned") || vm.can("patients.read_self");
      };
      vm.canReadMedicalHistories = function () {
        return vm.can("medical_histories.read_assigned") ||
          vm.can("medical_histories.read_self");
      };
      vm.canReadAppointments = function () {
        return vm.can("appointments.read") || vm.can("appointments.read_assigned") ||
          vm.can("appointments.read_self");
      };
      vm.canCreateAppointment = function () {
        return vm.can("appointments.create") || vm.can("appointments.create_self");
      };
      vm.canReadEncounters = function () {
        return vm.can("encounters.read_assigned") || vm.can("encounters.read_self");
      };
      vm.encounterStatusName = function (status) {
        return { in_progress: "Đang khám", completed: "Đã hoàn tất", cancelled: "Đã hủy" }[status] || status;
      };
      vm.orderStatusName = function (status) {
        return { ordered: "Đã chỉ định", in_progress: "Đang thực hiện", completed: "Có kết quả", cancelled: "Đã hủy" }[status] || status;
      };
      vm.orderTypeName = function (type) {
        return { laboratory: "Xét nghiệm", imaging: "Chẩn đoán hình ảnh", other: "Khác" }[type] || type;
      };
      vm.clinicalActionName = function (action) {
        return { start: "Bắt đầu khám", save: "Lưu bệnh án", complete: "Hoàn tất khám",
          order_create: "Thêm chỉ định", order_update: "Sửa chỉ định", order_cancel: "Hủy chỉ định",
          order_delete: "Xóa chỉ định", result_create: "Nhập kết quả", result_update: "Sửa kết quả",
          result_delete: "Xóa kết quả" }[action] || action;
      };
      vm.canEditEncounter = function (permission) {
        return vm.selectedEncounter && vm.selectedEncounter.status === "in_progress" && vm.can(permission);
      };
      vm.encounterDirty = function () {
        return !angular.equals(vm.encounterForm, encounterFormBaseline);
      };
      function clinicalUrl() {
        return "/encounters/" + encodeURIComponent(vm.selectedEncounter.encounter_id);
      }
      function setEncounter(item) {
        vm.selectedEncounter = item;
        vm.encounterForm = {
          chief_complaint: item.chief_complaint, clinical_notes: item.clinical_notes,
          diagnosis_summary: item.diagnosis_summary, treatment_plan: item.treatment_plan,
          vital_signs: angular.copy(item.vital_signs),
          diagnoses: item.diagnoses.map(function (d) {
            return { code: d.code, name: d.name, is_primary: d.is_primary, notes: d.notes };
          }),
        };
        encounterFormBaseline = angular.copy(vm.encounterForm);
        vm.orderForm = null;
        vm.resultForm = null;
      }
      vm.loadEncounters = function (page, keepMessage) {
        if (!vm.canReadEncounters()) { return; }
        if (!keepMessage) { vm.clearMessage(); }
        return api("GET", "/encounters", null, { params: {
          page: page, page_size: 20, search: vm.encounterFilters.search || undefined,
          status: vm.encounterFilters.status || undefined,
          date_from: vm.encounterFilters.date_from || undefined,
          date_to: vm.encounterFilters.date_to || undefined,
          sort_by: vm.encounterFilters.sort_by, sort_order: vm.encounterFilters.sort_order,
        } }).then(function (response) { vm.encounters = response.data; }, fail);
      };
      vm.loadClinicalQueue = function (page) {
        if (!vm.can("encounters.create_assigned") || !vm.can("appointments.read_assigned")) { return; }
        return api("GET", "/appointments", null, { params: {
          status: "checked_in", sort_order: "asc", page: page, page_size: 20,
        } }).then(function (response) { vm.clinicalQueue = response.data; }, fail);
      };
      vm.openEncounter = function (item) {
        if (!vm.canReadEncounters()) { return; }
        if (vm.encounterDirty() && !$window.confirm("Bệnh án có thay đổi chưa lưu. Mở bệnh án khác?")) { return; }
        vm.clearMessage();
        var current = ++encounterDetailRequest;
        return api("GET", "/encounters/" + encodeURIComponent(item.encounter_id)).then(function (response) {
          if (current !== encounterDetailRequest) { return; }
          setEncounter(response.data);
          vm.showEncounterVersions = false;
          vm.encounterHistories = [];
          if (vm.canReadMedicalHistories()) {
            api("GET", "/patients/" + encodeURIComponent(response.data.patient_id) + "/medical-histories",
              null, { params: { is_active: true, page_size: 100 } }).then(function (histories) {
                if (current === encounterDetailRequest) { vm.encounterHistories = histories.data.items; }
              }, fail);
          }
        }, fail);
      };
      vm.encounterFromAppointment = function (item) {
        if (!vm.canReadEncounters()) { return; }
        vm.open("encounters");
        return api("GET", "/encounters", null, { params: { appointment_id: item.appointment_id } })
          .then(function (response) {
            if (response.data.items.length) { vm.openEncounter(response.data.items[0]); }
            else { vm.error = "Bệnh án chưa được hoàn tất hoặc không có trong phạm vi được xem."; }
          }, fail);
      };
      vm.startEncounter = function (item) {
        if (!vm.can("encounters.create_assigned") || item.status !== "checked_in") { return; }
        if (!$window.confirm("Bắt đầu khám cho " + item.patient_name + "?")) { return; }
        if (vm.encounterDirty() && !$window.confirm("Bệnh án hiện tại có thay đổi chưa lưu. Tiếp tục mở lượt khám mới?")) { return; }
        return run(function () {
          return api("POST", "/encounters", { appointment_id: item.appointment_id,
            appointment_version: item.version, chief_complaint: item.reason || null });
        }, function (response) {
          vm.screen = "encounters";
          vm.message = "Đã bắt đầu khám.";
          setEncounter(response);
          vm.openEncounter(response);
          vm.loadEncounters(1, true);
          vm.loadClinicalQueue(1);
        });
      };
      vm.addDiagnosis = function () {
        vm.encounterForm.diagnoses.push({ name: "", code: null, notes: null,
          is_primary: !vm.encounterForm.diagnoses.length });
      };
      vm.setPrimaryDiagnosis = function (item) {
        vm.encounterForm.diagnoses.forEach(function (d) { d.is_primary = d === item; });
      };
      vm.saveEncounter = function (complete) {
        if (!vm.canEditEncounter("encounters.update_assigned")) { return; }
        if (complete && (!vm.can("encounters.complete_assigned") ||
            !$window.confirm("Lưu và hoàn tất khám? Sau đó bệnh án sẽ khóa chỉnh sửa."))) { return; }
        var payload = angular.copy(vm.encounterForm);
        payload.version = vm.selectedEncounter.version;
        return run(function () {
          return api("PUT", clinicalUrl(), payload).then(function (response) {
            setEncounter(response.data);
            if (complete) { return api("POST", clinicalUrl() + "/complete", { version: response.data.version }); }
            return response;
          });
        }, function (response) {
          setEncounter(response);
          vm.message = complete ? "Đã hoàn tất khám. Bệnh nhân có thể xem bệnh án." : "Đã lưu bệnh án.";
          vm.loadEncounters(vm.encounters.page, true);
          vm.loadClinicalQueue(1);
          if (vm.showEncounterVersions) { vm.loadEncounterVersions(1); }
        });
      };
      vm.clinicalClean = function () {
        if (vm.encounterDirty()) {
          vm.error = "Vui lòng lưu thay đổi bệnh án trước khi thao tác cận lâm sàng.";
          return false;
        }
        return true;
      };
      vm.startOrderForm = function (item) {
        if (!vm.canEditEncounter("clinical_orders.write_assigned") || !vm.clinicalClean()) { return; }
        vm.resultForm = null;
        vm.orderForm = item ? { order_id: item.order_id, order_version: item.version,
          order_type: item.order_type, name: item.name, instructions: item.instructions,
          status: item.status } : { order_type: "laboratory", status: "ordered" };
      };
      function clinicalSaved(response) {
        setEncounter(response);
        vm.message = "Đã cập nhật cận lâm sàng.";
        vm.loadEncounters(vm.encounters.page, true);
        if (vm.showEncounterVersions) { vm.loadEncounterVersions(1); }
      }
      vm.saveOrder = function () {
        if (!vm.orderForm || !vm.canEditEncounter("clinical_orders.write_assigned") || !vm.clinicalClean()) { return; }
        var form = vm.orderForm, payload = { version: vm.selectedEncounter.version,
          order_type: form.order_type, name: form.name, instructions: form.instructions || null };
        if (form.order_id) { payload.order_version = form.order_version; payload.status = form.status; }
        return run(function () {
          return api(form.order_id ? "PUT" : "POST", clinicalUrl() + "/clinical-orders" +
            (form.order_id ? "/" + encodeURIComponent(form.order_id) : ""), payload);
        }, clinicalSaved);
      };
      vm.removeOrder = function (item, action) {
        if (!vm.canEditEncounter("clinical_orders.write_assigned") || !vm.clinicalClean() ||
            !$window.confirm((action === "delete" ? "Xóa" : "Hủy") + " chỉ định " + item.name + "?")) { return; }
        return run(function () {
          return api(action === "delete" ? "DELETE" : "POST", clinicalUrl() + "/clinical-orders/" +
            encodeURIComponent(item.order_id) + (action === "delete" ? "" : "/cancel"),
            { version: vm.selectedEncounter.version, order_version: item.version });
        }, clinicalSaved);
      };
      vm.startResultForm = function (order, result) {
        if (!vm.canEditEncounter("clinical_results.write_assigned") || !vm.clinicalClean()) { return; }
        vm.orderForm = null;
        vm.resultForm = { order_id: order.order_id, order_name: order.name, order_version: order.version,
          result_id: result ? result.result_id : null, result_version: result ? result.version : null,
          result_text: result ? result.result_text : null,
          numeric_value: result && result.numeric_value !== null ? Number(result.numeric_value) : null,
          unit: result ? result.unit : null, reference_range: result ? result.reference_range : null };
      };
      vm.saveResult = function () {
        if (!vm.resultForm || !vm.canEditEncounter("clinical_results.write_assigned") || !vm.clinicalClean()) { return; }
        var form = vm.resultForm, payload = { version: vm.selectedEncounter.version,
          order_version: form.order_version, result_text: form.result_text || null,
          numeric_value: form.numeric_value, unit: form.unit || null, reference_range: form.reference_range || null };
        if (form.result_id) { payload.result_version = form.result_version; }
        return run(function () {
          return api(form.result_id ? "PUT" : "POST", clinicalUrl() + "/clinical-orders/" +
            encodeURIComponent(form.order_id) + "/results" + (form.result_id ? "/" + encodeURIComponent(form.result_id) : ""), payload);
        }, clinicalSaved);
      };
      vm.removeResult = function (order, result) {
        if (!vm.canEditEncounter("clinical_results.write_assigned") || !vm.clinicalClean() ||
            !$window.confirm("Xóa kết quả này? Kết quả cũ vẫn được lưu trong lịch sử bệnh án.")) { return; }
        return run(function () {
          return api("DELETE", clinicalUrl() + "/clinical-orders/" + encodeURIComponent(order.order_id) +
            "/results/" + encodeURIComponent(result.result_id), { version: vm.selectedEncounter.version,
              order_version: order.version, result_version: result.version });
        }, clinicalSaved);
      };
      vm.loadEncounterVersions = function (page) {
        if (!vm.selectedEncounter || !vm.can("record_versions.read_assigned")) { return; }
        return api("GET", clinicalUrl() + "/versions", null, { params: { page: page, page_size: 10 } })
          .then(function (response) { vm.encounterVersions = response.data; vm.showEncounterVersions = true; }, fail);
      };
      vm.canReadReception = function () {
        return vm.can("appointments.check_in") && vm.can("appointments.read");
      };
      vm.canReceiveAppointment = function (item, action) {
        if (!vm.can("appointments.read") || ["booked", "confirmed"].indexOf(item.status) < 0) {
          return false;
        }
        if (action === "confirm") {
          return vm.can("appointments.update") && item.status === "booked" &&
            new Date(item.appointment_at).getTime() > Date.now();
        }
        if (!vm.can("appointments.check_in")) { return false; }
        if (action === "check-in") {
          return clinicDate(item.appointment_at) === clinicDate(Date.now());
        }
        return action === "no-show" && new Date(item.ends_at).getTime() <= Date.now();
      };
      vm.loadReception = function (page, keepMessage) {
        if (!vm.canReadReception()) { return; }
        if (!keepMessage) { vm.clearMessage(); }
        var current = ++receptionRequestVersion;
        vm.receptionLoading = true;
        return api("GET", "/reception", null, { params: {
          work_date: vm.receptionFilters.work_date || undefined,
          search: vm.receptionFilters.search || undefined,
          doctor_id: vm.receptionFilters.doctor_id || undefined,
          status: vm.receptionFilters.status || undefined,
          sort_order: vm.receptionFilters.sort_order, page: page, page_size: 20,
        } }).then(function (response) {
          if (current === receptionRequestVersion) { vm.reception = response.data; }
        }, function (error) {
          if (current === receptionRequestVersion) { fail(error); }
        }).finally(function () {
          if (current === receptionRequestVersion) { vm.receptionLoading = false; }
        });
      };
      vm.receiveAppointment = function (item, action) {
        if (!vm.canReceiveAppointment(item, action)) { return; }
        var labels = { confirm: "Xác nhận lịch", "check-in": "Check-in", "no-show": "Đánh dấu vắng hẹn" };
        if (!$window.confirm(labels[action] + " cho " + item.patient_name + "?")) { return; }
        return run(function () {
          return api("POST", "/appointments/" + encodeURIComponent(item.appointment_id) + "/" + action,
            { version: item.version });
        }, function (response) {
          angular.extend(item, response);
          vm.message = labels[action] + " thành công.";
          if (vm.screen === "reception") { vm.loadReception(vm.reception.page, true); }
        });
      };
      vm.receptionPatient = function (item) {
        if (!vm.canReadPatients()) { return; }
        vm.clearMessage();
        vm.screen = "patients";
        vm.loadPatients(1, true);
        vm.openPatient(item);
      };
      vm.canChangeAppointment = function (item, action) {
        return (vm.can("appointments." + action) || vm.can("appointments." + action + "_self")) &&
          ["booked", "confirmed"].indexOf(item.status) >= 0 &&
          new Date(item.appointment_at).getTime() > Date.now();
      };
      vm.appointmentStatusName = function (status) {
        return {
          booked: "Đã đặt", confirmed: "Đã xác nhận", checked_in: "Đã đến",
          in_progress: "Đang khám", completed: "Đã khám", cancelled: "Đã hủy", no_show: "Vắng hẹn",
        }[status] || status;
      };
      vm.clinicDateTime = function (value) {
        return value ? new Date(value).toLocaleString("vi-VN", { timeZone: "Asia/Ho_Chi_Minh" }) : "";
      };
      function clinicDate(value) {
        var d = new Date(new Date(value).getTime() + 7 * 60 * 60 * 1000);
        return d.toISOString().slice(0, 10);
      }
      vm.historyTypeName = function (type) {
        return {
          allergy: "Dị ứng",
          condition: "Bệnh lý",
          surgery: "Phẫu thuật",
          family: "Tiền sử gia đình",
          medication: "Thuốc đang dùng",
          other: "Khác",
        }[type] || type;
      };
      vm.open = function (screen) {
        if (screen === "users" && !vm.can("users.read")) {
          return;
        }
        if (screen === "roles" && !vm.can("roles.read")) {
          return;
        }
        if (screen === "patients" && !vm.canReadPatients()) {
          return;
        }
        if (screen === "appointments" && !vm.canReadAppointments()) {
          return;
        }
        if (screen === "reception" && !vm.canReadReception()) { return; }
        if (screen === "encounters" && !vm.canReadEncounters()) { return; }
        if (["home", "users", "roles", "patients", "appointments", "reception", "encounters"].indexOf(screen) < 0) {
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
        if (screen === "patients") {
          vm.selectedPatient = null;
          vm.medicalHistories = { items: [], page: 1, page_size: 10, total: 0 };
          vm.loadPatients(1);
        }
        if (screen === "appointments") {
          vm.loadAppointments(1);
          vm.loadDoctors();
        }
        if (screen === "reception") {
          vm.loadReception(1);
          vm.loadDoctors();
        }
        if (screen === "encounters") {
          vm.loadEncounters(1);
          vm.loadClinicalQueue(1);
        }
      };
      vm.reloadMe = function (notify) {
        return api("GET", "/auth/me").then(function (response) {
          vm.user = response.data;
          vm.session.user = response.data;
          saveSession(vm.session);
          if (
            (vm.screen === "users" && !vm.can("users.read")) ||
            (vm.screen === "roles" && !vm.can("roles.read")) ||
            (vm.screen === "patients" && !vm.canReadPatients()) ||
            (vm.screen === "appointments" && !vm.canReadAppointments()) ||
            (vm.screen === "reception" && !vm.canReadReception()) ||
            (vm.screen === "encounters" && !vm.canReadEncounters())
          ) {
            vm.screen = "home";
            vm.selectedPatient = null;
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
          function () {
            vm.message = "If this email is registered, we have sent a reset code.";
          },
        );
      };
      vm.reset = function () {
        return run(
          function () {
            return $http.post(apiRoot + "/auth/reset-password", vm.resetForm);
          },
          function () {
            vm.authScreen = "login";
            vm.resetForm = {};
            vm.message = "Password updated. Please sign in again.";
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
      vm.loadAppointments = function (page, keepMessage) {
        if (!vm.canReadAppointments()) { return; }
        if (!keepMessage) { vm.clearMessage(); }
        return api("GET", "/appointments", null, { params: {
          page: page, page_size: 20, search: vm.appointmentFilters.search || undefined,
          status: vm.appointmentFilters.status || undefined,
          doctor_id: vm.appointmentFilters.doctor_id || undefined,
          date_from: vm.appointmentFilters.date_from || undefined,
          date_to: vm.appointmentFilters.date_to || undefined,
          sort_by: vm.appointmentFilters.sort_by, sort_order: vm.appointmentFilters.sort_order,
        } }).then(function (response) { vm.appointments = response.data; }, fail);
      };
      vm.loadDoctors = function () {
        if (!vm.can("doctors.read")) { return; }
        return api("GET", "/doctors", null, { params: {
          page_size: 100, search: vm.doctorSearch || undefined,
        } }).then(function (response) { vm.doctors = response.data.items; }, fail);
      };
      vm.findBookingPatients = function () {
        if (!vm.can("appointments.create")) { return; }
        return api("GET", "/patients", null, { params: {
          page_size: 20, search: vm.bookingPatientSearch || undefined,
        } }).then(function (response) { vm.bookingPatients = response.data.items; }, fail);
      };
      vm.startAppointmentForm = function (item) {
        if (item && !vm.canChangeAppointment(item, "update")) { return; }
        if (!item && !vm.canCreateAppointment()) { return; }
        vm.clearMessage();
        vm.cancelAppointmentForm = null;
        vm.showScheduleForm = false;
        vm.slots = [];
        vm.appointmentForm = {};
        slotRequestVersion += 1;
        if (item) {
          return api("GET", "/appointments/" + encodeURIComponent(item.appointment_id))
            .then(function (response) {
              vm.appointmentForm = angular.copy(response.data);
              vm.appointmentForm.booking_date = clinicDate(response.data.appointment_at);
              vm.showAppointmentForm = true;
              vm.loadBookingSlots(response.data.appointment_at);
            }, fail);
        }
        vm.appointmentForm = { booking_date: clinicDate(Date.now()) };
        vm.showAppointmentForm = true;
        if (vm.can("appointments.create")) { vm.findBookingPatients(); }
      };
      vm.closeAppointmentForm = function () {
        vm.showAppointmentForm = false;
        vm.slots = [];
        slotRequestVersion += 1;
      };
      vm.loadBookingSlots = function (keepTime) {
        var form = vm.appointmentForm;
        var requestVersion = ++slotRequestVersion;
        form.slot_key = "";
        vm.slots = [];
        vm.slotsLoading = false;
        if (!form.doctor_id || !form.booking_date ||
            (vm.can("appointments.create") && !form.patient_id)) { return; }
        vm.slotsLoading = true;
        return api("GET", "/doctors/" + encodeURIComponent(form.doctor_id) + "/slots", null,
          { params: {
            work_date: form.booking_date, patient_id: form.patient_id || undefined,
            exclude_appointment_id: form.appointment_id || undefined,
          } }).then(function (response) {
          if (requestVersion !== slotRequestVersion) { return; }
          vm.slots = response.data.items.map(function (slot) {
            slot.key = slot.schedule_id + "|" + slot.appointment_at;
            slot.label = new Date(slot.appointment_at).toLocaleTimeString("vi-VN", {
              hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh",
            }) + " – " + new Date(slot.ends_at).toLocaleTimeString("vi-VN", {
              hour: "2-digit", minute: "2-digit", timeZone: "Asia/Ho_Chi_Minh",
            });
            if (keepTime && slot.available &&
                new Date(slot.appointment_at).getTime() === new Date(keepTime).getTime()) {
              form.slot_key = slot.key;
            }
            return slot;
          });
        }, function (error) {
          if (requestVersion === slotRequestVersion) { fail(error); }
        }).finally(function () {
          if (requestVersion === slotRequestVersion) { vm.slotsLoading = false; }
        });
      };
      vm.saveAppointment = function () {
        var form = vm.appointmentForm;
        var slot = vm.slots.filter(function (s) { return s.key === form.slot_key && s.available; })[0];
        if (!slot || vm.slotsLoading) { return; }
        var editing = !!form.appointment_id;
        var payload = {
          doctor_id: form.doctor_id, schedule_id: slot.schedule_id,
          appointment_at: slot.appointment_at, reason: form.reason || null,
        };
        if (editing) { payload.version = form.version; }
        else if (vm.can("appointments.create")) { payload.patient_id = form.patient_id; }
        return run(function () {
          return api(editing ? "PUT" : "POST", "/appointments" +
            (editing ? "/" + encodeURIComponent(form.appointment_id) : ""), payload);
        }, function () {
          vm.closeAppointmentForm();
          vm.message = editing ? "Đã đổi lịch hẹn." : "Đã đặt lịch hẹn.";
          vm.loadAppointments(1, true);
        });
      };
      vm.startCancelAppointment = function (item) {
        if (!vm.canChangeAppointment(item, "cancel")) { return; }
        vm.clearMessage();
        vm.closeAppointmentForm();
        vm.cancelAppointmentForm = angular.copy(item);
        vm.cancelAppointmentForm.cancellation_reason = "";
      };
      vm.cancelAppointment = function () {
        var form = vm.cancelAppointmentForm;
        if (!form) { return; }
        return run(function () {
          return api("POST", "/appointments/" + encodeURIComponent(form.appointment_id) + "/cancel", {
            version: form.version, cancellation_reason: form.cancellation_reason,
          });
        }, function () {
          vm.cancelAppointmentForm = null;
          vm.message = "Đã hủy lịch hẹn. Khung giờ được mở lại.";
          vm.loadAppointments(vm.appointments.page, true);
        });
      };
      vm.loadSchedules = function (page, keepMessage) {
        if (!vm.can("doctor_schedules.read")) { return; }
        if (!keepMessage) { vm.clearMessage(); }
        vm.showSchedules = true;
        return api("GET", "/doctor-schedules", null, { params: {
          page: page, page_size: 20, doctor_id: vm.scheduleDoctorFilter || undefined,
          date_from: vm.scheduleDateFilter || clinicDate(Date.now()),
          date_to: vm.scheduleDateFilter || undefined,
        } }).then(function (response) { vm.schedules = response.data; }, fail);
      };
      vm.startScheduleForm = function () {
        if (!vm.can("doctor_schedules.manage")) { return; }
        vm.clearMessage();
        vm.closeAppointmentForm();
        vm.cancelAppointmentForm = null;
        vm.scheduleForm = {
          work_date: clinicDate(Date.now()), start_time: "08:00", end_time: "17:00", slot_minutes: 30,
        };
        vm.showScheduleForm = true;
        vm.loadSchedules(1, true);
      };
      vm.saveSchedule = function () {
        var form = vm.scheduleForm;
        return run(function () {
          return api("POST", "/doctor-schedules", {
            doctor_id: form.doctor_id, slot_minutes: Number(form.slot_minutes),
            start_at: form.work_date + "T" + form.start_time + ":00+07:00",
            end_at: form.work_date + "T" + form.end_time + ":00+07:00",
          });
        }, function () {
          vm.showScheduleForm = false;
          vm.message = "Đã tạo ca làm. Bệnh nhân có thể đặt các khung giờ trong ca.";
          vm.loadSchedules(1, true);
        });
      };
      vm.cancelSchedule = function (item) {
        if (!vm.can("doctor_schedules.manage") ||
            !$window.confirm("Hủy ca làm này? Ca có lịch hẹn đang hoạt động sẽ không thể hủy.")) { return; }
        return run(function () {
          return api("POST", "/doctor-schedules/" + encodeURIComponent(item.schedule_id) + "/cancel", {
            version: item.version,
          });
        }, function () {
          vm.message = "Đã hủy ca làm.";
          vm.loadSchedules(vm.schedules.page, true);
        });
      };
      vm.loadPatients = function (page, keepMessage) {
        if (!vm.canReadPatients()) {
          vm.screen = "home";
          return;
        }
        if (!keepMessage) {
          vm.clearMessage();
        }
        return api("GET", "/patients", null, {
          params: {
            page: page,
            page_size: 20,
            search: vm.patientFilters.search || undefined,
            gender: vm.patientFilters.gender || undefined,
            has_account: vm.patientFilters.has_account === ""
              ? undefined : vm.patientFilters.has_account,
            sort_by: vm.patientFilters.sort_by,
            sort_order: vm.patientFilters.sort_order,
          },
        }).then(function (response) {
          vm.patients = response.data;
          if (vm.can("patients.read_self") && vm.patients.items.length) {
            vm.openPatient(vm.patients.items[0]);
          }
        }, fail);
      };
      vm.openPatient = function (item) {
        return api("GET", "/patients/" + encodeURIComponent(item.patient_id))
          .then(function (response) {
            vm.selectedPatient = response.data;
            vm.showPatientForm = false;
            vm.showHistoryForm = false;
            vm.historyFilters = {
              type: "", is_active: "", search: "", sort_by: "created_at", sort_order: "desc",
            };
            vm.medicalHistories = { items: [], page: 1, page_size: 10, total: 0 };
            if (vm.canReadMedicalHistories()) {
              vm.loadMedicalHistories(1, true);
            }
          }, fail);
      };
      vm.loadMedicalHistories = function (page, keepMessage) {
        if (!vm.selectedPatient || !vm.canReadMedicalHistories()) {
          return;
        }
        if (!keepMessage) {
          vm.clearMessage();
        }
        return api("GET", "/patients/" + encodeURIComponent(vm.selectedPatient.patient_id) +
          "/medical-histories", null, {
          params: {
            page: page,
            page_size: 10,
            type: vm.historyFilters.type || undefined,
            is_active: vm.historyFilters.is_active === ""
              ? undefined : vm.historyFilters.is_active,
            search: vm.historyFilters.search || undefined,
            sort_by: vm.historyFilters.sort_by,
            sort_order: vm.historyFilters.sort_order,
          },
        }).then(function (response) {
          vm.medicalHistories = response.data;
        }, fail);
      };
      vm.startHistoryForm = function (item) {
        if (!vm.can("medical_histories.write_assigned") || !vm.selectedPatient) {
          return;
        }
        vm.historyForm = item ? angular.copy(item) : { type: "allergy", is_active: true };
        vm.showHistoryForm = true;
        vm.clearMessage();
      };
      vm.saveHistory = function () {
        if (!vm.can("medical_histories.write_assigned") || !vm.selectedPatient) {
          return;
        }
        var patientId = encodeURIComponent(vm.selectedPatient.patient_id);
        var payload = angular.copy(vm.historyForm);
        var editing = !!payload.history_id;
        payload.description = payload.description || null;
        payload.onset_date = payload.onset_date || null;
        return run(function () {
          return api(editing ? "PUT" : "POST", "/patients/" + patientId +
            "/medical-histories" +
            (editing ? "/" + encodeURIComponent(payload.history_id) : ""), payload);
        }, function () {
          vm.showHistoryForm = false;
          vm.historyForm = {};
          vm.message = editing ? "Đã cập nhật tiền sử bệnh." : "Đã thêm tiền sử bệnh.";
          vm.loadMedicalHistories(vm.medicalHistories.page, true);
        });
      };
      vm.deleteHistory = function (item) {
        if (!vm.can("medical_histories.write_assigned") || !vm.selectedPatient ||
            !$window.confirm("Xóa mục tiền sử bệnh này?")) {
          return;
        }
        return run(function () {
          return api("DELETE", "/patients/" +
            encodeURIComponent(vm.selectedPatient.patient_id) + "/medical-histories/" +
            encodeURIComponent(item.history_id), null, { params: { version: item.version } });
        }, function () {
          vm.message = "Đã xóa mục tiền sử bệnh.";
          vm.loadMedicalHistories(1, true);
        });
      };
      vm.startPatientForm = function (item) {
        if (!vm.can(item ? "patients.update" : "patients.create")) {
          return;
        }
        vm.patientForm = item ? angular.copy(item) : {};
        vm.showPatientForm = true;
        vm.clearMessage();
      };
      vm.savePatient = function () {
        var editing = !!vm.patientForm.patient_id;
        if (!vm.can(editing ? "patients.update" : "patients.create")) {
          return;
        }
        var payload = angular.copy(vm.patientForm);
        ["date_of_birth", "gender", "phone", "email", "address", "insurance_number"]
          .forEach(function (field) {
            payload[field] = payload[field] || null;
          });
        return run(function () {
          return api(
            editing ? "PUT" : "POST",
            editing ? "/patients/" + encodeURIComponent(payload.patient_id) : "/patients",
            payload,
          );
        }, function (saved) {
          vm.selectedPatient = saved;
          vm.patientForm = {};
          vm.showPatientForm = false;
          vm.message = editing ? "Đã cập nhật bệnh nhân." : "Đã thêm bệnh nhân.";
          vm.loadPatients(vm.patients.page, true);
        });
      };
      vm.deletePatient = function (item) {
        if (!vm.can("patients.delete") ||
            !$window.confirm("Xóa hồ sơ bệnh nhân " + item.patient_code + "?")) {
          return;
        }
        return run(function () {
          return api("DELETE", "/patients/" + encodeURIComponent(item.patient_id),
            null, { params: { version: item.version } });
        }, function () {
          vm.selectedPatient = null;
          vm.showPatientForm = false;
          vm.message = "Đã xóa hồ sơ bệnh nhân.";
          vm.loadPatients(1, true);
        });
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
