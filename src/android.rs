//! Android entry point (NativeActivity) and egui interface.

use std::time::{Duration, Instant};

use eframe::egui::{self, Align, Color32, FontId, Layout, RichText, TextStyle};
use jni::objects::{JObject, JValue};
use jni::JavaVM;
use winit::platform::android::activity::{AndroidApp, WindowManagerFlags};
use zeroize::Zeroize;

use crate::generator::{self, BITS_DEFAULT, BITS_MAX, BITS_MIN};

const ACCENT: Color32 = Color32::from_rgb(0x4f, 0xb3, 0x8a);

#[no_mangle]
fn android_main(app: AndroidApp) {
    // No screenshots, screen recording, or thumbnail in the recent apps list.
    app.set_window_flags(WindowManagerFlags::SECURE, WindowManagerFlags::empty());

    let options = eframe::NativeOptions {
        android_app: Some(app.clone()),
        ..Default::default()
    };
    let _ = eframe::run_native(
        "pwqgen",
        options,
        Box::new(|cc| Ok(Box::new(PwqgenApp::new(cc, app)))),
    );
}

struct PwqgenApp {
    android: AndroidApp,
    bits: i32,
    passphrase: String,
    status: Option<(String, Instant)>,
}

impl PwqgenApp {
    fn new(cc: &eframe::CreationContext<'_>, android: AndroidApp) -> Self {
        let ctx = &cc.egui_ctx;
        ctx.set_visuals(egui::Visuals::dark());
        ctx.all_styles_mut(|style| {
            style.text_styles = [
                (TextStyle::Heading, FontId::proportional(30.0)),
                (TextStyle::Body, FontId::proportional(18.0)),
                (TextStyle::Button, FontId::proportional(20.0)),
                (TextStyle::Small, FontId::proportional(14.0)),
                (TextStyle::Monospace, FontId::monospace(26.0)),
            ]
            .into();
            style.spacing.button_padding = egui::vec2(18.0, 12.0);
            style.spacing.slider_width = 220.0;
        });

        let mut app = Self {
            android,
            bits: BITS_DEFAULT,
            passphrase: String::new(),
            status: None,
        };
        app.regenerate();
        app
    }

    fn regenerate(&mut self) {
        self.passphrase.zeroize();
        match generator::generate(self.bits) {
            Some(p) => self.passphrase = p,
            None => self.set_status("Échec de la génération"),
        }
    }

    fn copy(&mut self) {
        match copy_to_clipboard(&self.passphrase) {
            Ok(()) => self.set_status("Copié ✓"),
            Err(_) => self.set_status("Impossible de copier"),
        }
    }

    fn set_status(&mut self, text: &str) {
        self.status = Some((text.to_owned(), Instant::now()));
    }

    /// Margins (in points) for the status and navigation bars.
    fn insets(&self, ctx: &egui::Context) -> (f32, f32) {
        let ppp = ctx.pixels_per_point();
        let rect = self.android.content_rect();
        let screen_height = ctx.content_rect().height() * ppp;
        let top = rect.top.max(0) as f32 / ppp;
        let bottom = (screen_height - rect.bottom as f32).max(0.0) / ppp;
        (top, bottom)
    }
}

impl Drop for PwqgenApp {
    fn drop(&mut self) {
        self.passphrase.zeroize();
    }
}

impl eframe::App for PwqgenApp {
    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        let ctx = ui.ctx().clone();
        let (top, bottom) = self.insets(&ctx);

        ui.add_space(top + 24.0);
        ui.with_layout(Layout::top_down(Align::Center), |ui| {
            ui.set_max_width((ui.available_width() - 32.0).max(0.0));

            ui.heading(RichText::new("pwqgen").color(ACCENT).strong());
            ui.label(RichText::new("Phrases de passe passwdqc").weak());
            ui.add_space(32.0);

            egui::Frame::group(ui.style())
                .inner_margin(20.0)
                .corner_radius(12.0)
                .show(ui, |ui| {
                    ui.set_width(ui.available_width());
                    ui.vertical_centered(|ui| {
                        ui.add(
                            egui::Label::new(
                                RichText::new(&self.passphrase).monospace().strong(),
                            )
                            .wrap()
                            .selectable(false),
                        );
                    });
                });

            ui.add_space(12.0);
            let words = self
                .passphrase
                .split(|c: char| !c.is_ascii_alphabetic())
                .filter(|w| !w.is_empty())
                .count();
            ui.label(
                RichText::new(format!(
                    "{} caractères · {} mots · {} bits d'entropie",
                    self.passphrase.len(),
                    words,
                    self.bits
                ))
                .small()
                .weak(),
            );

            ui.add_space(32.0);
            ui.label("Entropie (bits)");
            let slider = ui.add(egui::Slider::new(&mut self.bits, BITS_MIN..=BITS_MAX));
            if slider.drag_stopped() || (slider.changed() && !slider.dragged()) {
                self.regenerate();
            }
            ui.add_space(4.0);
            ui.horizontal(|ui| {
                ui.spacing_mut().item_spacing.x = 8.0;
                for (label, bits) in [("Défaut 47", BITS_DEFAULT), ("64", 64), ("80", 80), ("100", 100)] {
                    if ui.selectable_label(self.bits == bits, label).clicked() {
                        self.bits = bits;
                        self.regenerate();
                    }
                }
            });

            ui.add_space(32.0);
            ui.horizontal(|ui| {
                ui.spacing_mut().item_spacing.x = 16.0;
                if ui
                    .add(egui::Button::new("Nouvelle phrase").fill(ACCENT.gamma_multiply(0.6)))
                    .clicked()
                {
                    self.regenerate();
                }
                if ui.button("Copier").clicked() {
                    self.copy();
                }
            });

            ui.add_space(16.0);
            if let Some((text, at)) = &self.status {
                if at.elapsed() < Duration::from_secs(3) {
                    ui.label(RichText::new(text.as_str()).color(ACCENT));
                    ctx.request_repaint_after(Duration::from_millis(250));
                } else {
                    self.status = None;
                }
            }
        });

        ui.with_layout(Layout::bottom_up(Align::Center), |ui| {
            ui.add_space(bottom + 12.0);
            ui.label(
                RichText::new("Algorithme et liste de mots : passwdqc, Openwall")
                    .small()
                    .weak(),
            );
        });
    }
}

/// Copies `text` through Android's ClipboardManager, flagged as sensitive so
/// Android 13+ hides it in the clipboard preview.
fn copy_to_clipboard(text: &str) -> jni::errors::Result<()> {
    let ctx = ndk_context::android_context();
    // SAFETY: android-activity initialises ndk-context with valid pointers to
    // the JavaVM and the activity, which outlive this call.
    let vm = unsafe { JavaVM::from_raw(ctx.vm().cast())? };
    let activity = unsafe { JObject::from_raw(ctx.context().cast()) };
    let mut env = vm.attach_current_thread()?;

    let result = env.with_local_frame(16, |env| -> jni::errors::Result<()> {
        let service = env.new_string("clipboard")?;
        let clipboard = env
            .call_method(
                &activity,
                "getSystemService",
                "(Ljava/lang/String;)Ljava/lang/Object;",
                &[JValue::Object(&service)],
            )?
            .l()?;

        let label = env.new_string("pwqgen")?;
        let content = env.new_string(text)?;
        let clip = env
            .call_static_method(
                "android/content/ClipData",
                "newPlainText",
                "(Ljava/lang/CharSequence;Ljava/lang/CharSequence;)Landroid/content/ClipData;",
                &[JValue::Object(&label), JValue::Object(&content)],
            )?
            .l()?;

        let description = env
            .call_method(&clip, "getDescription", "()Landroid/content/ClipDescription;", &[])?
            .l()?;
        let extras = env.new_object("android/os/PersistableBundle", "()V", &[])?;
        let key = env.new_string("android.content.extra.IS_SENSITIVE")?;
        env.call_method(
            &extras,
            "putBoolean",
            "(Ljava/lang/String;Z)V",
            &[JValue::Object(&key), JValue::Bool(1)],
        )?;
        env.call_method(
            &description,
            "setExtras",
            "(Landroid/os/PersistableBundle;)V",
            &[JValue::Object(&extras)],
        )?;

        env.call_method(
            &clipboard,
            "setPrimaryClip",
            "(Landroid/content/ClipData;)V",
            &[JValue::Object(&clip)],
        )?;
        Ok(())
    });

    if env.exception_check().unwrap_or(false) {
        let _ = env.exception_clear();
    }
    result
}
