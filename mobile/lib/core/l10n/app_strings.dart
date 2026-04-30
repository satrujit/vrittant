import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'language_provider.dart';

/// Centralized UI strings for Odia and English.
///
/// Usage: `final s = AppStrings.of(ref);`
/// Then:  `s.home`, `s.newStory`, etc.
class AppStrings {
  final AppLanguage _lang;
  const AppStrings._(this._lang);

  /// Read the current language from Riverpod and return the matching strings.
  static AppStrings of(WidgetRef ref) {
    final lang = ref.watch(languageProvider);
    return AppStrings._(lang);
  }

  bool get isOdia => _lang == AppLanguage.odia;

  // ===========================================================================
  // Bottom Navigation
  // ===========================================================================
  String get navHome => isOdia ? '\u0B2E\u0B42\u0B33 \u0B2A\u0B43\u0B37\u0B4D\u0B20\u0B3E' : 'HOME';
  String get navMyNews => isOdia ? '\u0B2E\u0B4B \u0B16\u0B2C\u0B30' : 'MY NEWS';
  String get navAllStories => isOdia ? '\u0B38\u0B2E\u0B38\u0B4D\u0B24 \u0B16\u0B2C\u0B30' : 'ALL STORIES';
  String get navFiles => isOdia ? '\u0B2B\u0B3E\u0B07\u0B32' : 'FILES';
  String get navSettings => isOdia ? '\u0B38\u0B47\u0B1F\u0B3F\u0B02\u0B38' : 'SETTINGS';
  String get navProfile => isOdia ? '\u0B2A\u0B4D\u0B30\u0B4B\u0B2B\u0B3E\u0B07\u0B32\u0B4D' : 'Profile';

  // ===========================================================================
  // Home Screen
  // ===========================================================================
  String get goodMorning => isOdia ? '\u0B38\u0B41\u0B2A\u0B4D\u0B30\u0B2D\u0B3E\u0B24' : 'Good Morning';
  String get goodAfternoon => isOdia ? '\u0B36\u0B41\u0B2D \u0B05\u0B2A\u0B30\u0B3E\u0B39\u0B4D\u0B28' : 'Good Afternoon';
  String get goodEvening => isOdia ? '\u0B36\u0B41\u0B2D \u0B38\u0B28\u0B4D\u0B27\u0B4D\u0B5F\u0B3E' : 'Good Evening';
  String get reporter => isOdia ? '\u0B38\u0B3E\u0B2E\u0B4D\u0B2C\u0B3E\u0B26\u0B3F\u0B15' : 'Reporter';
  String get recentSubmissions => isOdia ? '\u0B38\u0B3E\u0B2E\u0B4D\u0B2A\u0B4D\u0B30\u0B24\u0B3F\u0B15 \u0B26\u0B3E\u0B16\u0B32' : 'Recent Submissions';
  String get seeAll => isOdia ? '\u0B38\u0B2C\u0B41 \u0B26\u0B47\u0B16\u0B28\u0B4D\u0B24\u0B41' : 'See All';
  String get searchStories => isOdia ? '\u0B16\u0B2C\u0B30 \u0B16\u0B4B\u0B1C\u0B28\u0B4D\u0B24\u0B41...' : 'Search stories...';
  String get all => isOdia ? '\u0B38\u0B2C\u0B41' : 'All';
  String get latestStories => isOdia ? '\u0B06\u0B1C\u0B3F\u0B30 \u0B16\u0B2C\u0B30' : "TODAY'S STORIES";
  String totalCount(int n) => isOdia ? '$n \u0B2E\u0B4B\u0B1F' : '$n Total';
  String get noStoriesToday => isOdia
      ? '\u0B06\u0B2A\u0B23 \u0B06\u0B1C\u0B3F \u0B15\u0B4C\u0B23\u0B38\u0B3F \u0B16\u0B2C\u0B30 \u0B2F\u0B4B\u0B21\u0B3C\u0B3F \u0B28\u0B3E\u0B39\u0B3E\u0B28\u0B4D\u0B24\u0B3F\u0964 \u0B06\u0B30\u0B2E\u0B4D\u0B2D \u0B15\u0B30\u0B3F\u0B2C\u0B3E \u0B2A\u0B3E\u0B07\u0B01 + \u0B2C\u0B1F\u0B28\u0B4D \u0B09\u0B2A\u0B30\u0B47 \u0B15\u0B4D\u0B32\u0B3F\u0B15\u0B4D \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41\u0964'
      : 'You have not added any news today.\nClick on the + icon to start.';

  // ===========================================================================
  // Create News / Notepad
  // ===========================================================================
  String get newStory => isOdia ? '\u0B28\u0B42\u0B06 \u0B16\u0B2C\u0B30' : 'New Story';
  String get submit => isOdia ? '\u0B26\u0B3E\u0B16\u0B32 \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Submit';
  String get storySubmitted => isOdia ? '\u0B16\u0B2C\u0B30 \u0B38\u0B2B\u0B33\u0B24\u0B3E\u0B30\u0B47 \u0B26\u0B3E\u0B16\u0B32 \u0B39\u0B47\u0B32\u0B3E!' : 'Story submitted successfully!';
  String get storySubmitFailed => isOdia ? '\u0B16\u0B2C\u0B30 \u0B26\u0B3E\u0B16\u0B32 \u0B2C\u0B3F\u0B2B\u0B33 \u0B39\u0B47\u0B32\u0B3E\u0964' : 'Story submission failed.';
  String get draft => isOdia ? '\u0B21\u0B4D\u0B30\u0B3E\u0B2B\u0B4D\u0B1F' : 'Draft';
  String get drafts => isOdia ? '\u0B21\u0B4D\u0B30\u0B3E\u0B2B\u0B4D\u0B1F' : 'Drafts';
  String get ready => isOdia ? '\u0B2A\u0B4D\u0B30\u0B38\u0B4D\u0B24\u0B41\u0B24' : 'Ready';
  String get untitledDraft => isOdia ? '\u0B36\u0B40\u0B30\u0B4D\u0B37\u0B15\u0B2C\u0B3F\u0B39\u0B40\u0B28 \u0B21\u0B4D\u0B30\u0B3E\u0B2B\u0B4D\u0B1F' : 'Untitled Draft';
  String get submitStoryTitle => isOdia ? '\u0B26\u0B3E\u0B16\u0B32 \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41?' : 'Submit story?';
  String get submitStoryConfirm => isOdia ? '\u0B0F\u0B39\u0B3F \u0B16\u0B2C\u0B30 \u0B26\u0B3E\u0B16\u0B32 \u0B15\u0B30\u0B3F\u0B2C\u0B3E\u0B15\u0B41 \u0B1A\u0B3E\u0B39\u0B41\u0B01\u0B1B\u0B28\u0B4D\u0B24\u0B3F?' : 'Do you want to submit this story?';
  String get deleteThisDraft => isOdia ? '\u0B0F\u0B39\u0B3F \u0B21\u0B4D\u0B30\u0B3E\u0B2B\u0B4D\u0B1F \u0B39\u0B1F\u0B3E\u0B07\u0B2C\u0B47?' : 'Delete this draft?';
  String get remove => isOdia ? '\u0B39\u0B1F\u0B3E\u0B28\u0B4D\u0B24\u0B41' : 'Remove';
  String get advancedSettings => isOdia ? '\u0B09\u0B28\u0B4D\u0B28\u0B24 \u0B38\u0B47\u0B1F\u0B3F\u0B02\u0B38' : 'Advanced Settings';
  String get autoCategory => isOdia ? '\u0B38\u0B4D\u0B71\u0B24\u0B03' : 'Auto';
  String get done => isOdia ? '\u0B39\u0B47\u0B32\u0B3E' : 'Done';
  String get attachingFile => isOdia ? '\u0B2B\u0B3E\u0B07\u0B32 \u0B2A\u0B4D\u0B30\u0B15\u0B4D\u0B30\u0B3F\u0B5F\u0B3E \u0B39\u0B47\u0B09\u0B1B\u0B3F...' : 'Processing file...';

  // ===========================================================================
  // Delete confirmations
  // ===========================================================================
  String get deleteAudioTitle => isOdia ? '\u0B05\u0B21\u0B3C\u0B3F\u0B13 \u0B21\u0B3F\u0B32\u0B3F\u0B1F\u0B4D \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41?' : 'Delete audio?';
  String get deleteAudioMsg => isOdia ? '\u0B0F\u0B39\u0B3F \u0B05\u0B21\u0B3C\u0B3F\u0B13 \u0B2C\u0B4D\u0B32\u0B15 \u0B38\u0B4D\u0B25\u0B3E\u0B5F\u0B40 \u0B2D\u0B3E\u0B2C\u0B30\u0B47 \u0B21\u0B3F\u0B32\u0B3F\u0B1F\u0B4D \u0B39\u0B47\u0B2C\u0964' : 'This audio block will be permanently deleted.';
  String get deletePhotoTitle => isOdia ? '\u0B2B\u0B1F\u0B4B \u0B21\u0B3F\u0B32\u0B3F\u0B1F\u0B4D \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41?' : 'Delete photo?';
  String get deletePhotoMsg => isOdia ? '\u0B0F\u0B39\u0B3F \u0B2B\u0B1F\u0B4B \u0B2C\u0B4D\u0B32\u0B15 \u0B38\u0B4D\u0B25\u0B3E\u0B5F\u0B40 \u0B2D\u0B3E\u0B2C\u0B30\u0B47 \u0B21\u0B3F\u0B32\u0B3F\u0B1F\u0B4D \u0B39\u0B47\u0B2C\u0964' : 'This photo block will be permanently deleted.';
  String get deleteVideoTitle => isOdia ? '\u0B2D\u0B3F\u0B21\u0B3F\u0B13 \u0B21\u0B3F\u0B32\u0B3F\u0B1F\u0B4D \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41?' : 'Delete video?';
  String get deleteVideoMsg => isOdia ? '\u0B0F\u0B39\u0B3F \u0B2D\u0B3F\u0B21\u0B3F\u0B13 \u0B2C\u0B4D\u0B32\u0B15 \u0B38\u0B4D\u0B25\u0B3E\u0B5F\u0B40 \u0B2D\u0B3E\u0B2C\u0B30\u0B47 \u0B21\u0B3F\u0B32\u0B3F\u0B1F\u0B4D \u0B39\u0B47\u0B2C\u0964' : 'This video block will be permanently deleted.';
  String get deleteDocTitle => isOdia ? '\u0B28\u0B25\u0B3F\u0B2A\u0B24\u0B4D\u0B30 \u0B21\u0B3F\u0B32\u0B3F\u0B1F\u0B4D \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41?' : 'Delete document?';
  String get deleteDocMsg => isOdia ? '\u0B0F\u0B39\u0B3F \u0B28\u0B25\u0B3F\u0B2A\u0B24\u0B4D\u0B30 \u0B2C\u0B4D\u0B32\u0B15 \u0B38\u0B4D\u0B25\u0B3E\u0B5F\u0B40 \u0B2D\u0B3E\u0B2C\u0B30\u0B47 \u0B21\u0B3F\u0B32\u0B3F\u0B1F\u0B4D \u0B39\u0B47\u0B2C\u0964' : 'This document block will be permanently deleted.';
  String get deleteFileTitle => isOdia ? '\u0B2B\u0B3E\u0B07\u0B32 \u0B21\u0B3F\u0B32\u0B3F\u0B1F\u0B4D \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41?' : 'Delete file?';
  String get deleteFileMsg => isOdia ? '\u0B0F\u0B39\u0B3F \u0B2B\u0B3E\u0B07\u0B32 \u0B2C\u0B4D\u0B32\u0B15 \u0B38\u0B4D\u0B25\u0B3E\u0B5F\u0B40 \u0B2D\u0B3E\u0B2C\u0B30\u0B47 \u0B21\u0B3F\u0B32\u0B3F\u0B1F\u0B4D \u0B39\u0B47\u0B2C\u0964' : 'This file block will be permanently deleted.';
  String get deleteBtn => isOdia ? '\u0B21\u0B3F\u0B32\u0B3F\u0B1F\u0B4D' : 'Delete';

  // ===========================================================================
  // Common actions
  // ===========================================================================
  String get cancel => isOdia ? '\u0B2C\u0B3E\u0B24\u0B3F\u0B32' : 'Cancel';
  String get yes => isOdia ? '\u0B39\u0B01' : 'Yes';
  String get no => isOdia ? '\u0B28\u0B3E\u0B39\u0B3F\u0B01' : 'No';
  String get ok => isOdia ? '\u0B20\u0B3F\u0B15\u0B4D' : 'OK';
  String get retry => isOdia ? '\u0B2A\u0B41\u0B23\u0B3F \u0B1A\u0B47\u0B37\u0B4D\u0B1F\u0B3E \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Retry';

  // ===========================================================================
  // Voice / Recording
  // ===========================================================================
  String get odiaLanguageLabel => '\u0B13\u0B21\u0B3C\u0B3F\u0B06';
  String get listening => isOdia ? '\u0B36\u0B41\u0B23\u0B41\u0B1B\u0B3F...' : 'Listening...';
  String get transcribingSpeech => isOdia ? '\u0B2C\u0B3E\u0B23\u0B40 \u0B32\u0B3F\u0B2A\u0B3F\u0B2C\u0B26\u0B4D\u0B27 \u0B39\u0B47\u0B09\u0B1B\u0B3F...' : 'Transcribing speech...';
  String get generatingHeadline => isOdia ? '\u0B1F\u0B3E\u0B07\u0B1F\u0B32\u0B4D \u0B24\u0B3F\u0B06\u0B30\u0B3F \u0B39\u0B47\u0B09\u0B1B\u0B3F...' : 'Generating headline...';
  String get aiGeneratedHeadline => isOdia ? 'AI \u0B1F\u0B3E\u0B07\u0B1F\u0B32\u0B4D' : 'AI-Generated Headline';
  String get transcribedText => isOdia ? '\u0B32\u0B3F\u0B2A\u0B3F\u0B2C\u0B26\u0B4D\u0B27 \u0B2A\u0B3E\u0B20' : 'Transcribed Text';
  String get englishTranslation => isOdia ? '\u0B07\u0B02\u0B30\u0B3E\u0B1C\u0B40 \u0B05\u0B28\u0B41\u0B2C\u0B3E\u0B26' : 'English Translation';
  String get translate => isOdia ? '\u0B05\u0B28\u0B41\u0B2C\u0B3E\u0B26' : 'Translate';
  String get rephrase => isOdia ? '\u0B2A\u0B41\u0B28\u0B03\u0B32\u0B47\u0B16\u0B28' : 'Rephrase';
  String get listen => isOdia ? '\u0B36\u0B41\u0B23\u0B28\u0B4D\u0B24\u0B41' : 'Listen';
  String get recording => isOdia ? '\u0B30\u0B47\u0B15\u0B30\u0B4D\u0B21\u0B3C\u0B3F\u0B02 \u0B1A\u0B3E\u0B32\u0B41\u0B1B\u0B3F' : 'Recording';
  String get liveTranscript => isOdia ? '\u0B38\u0B3F\u0B27\u0B3E \u0B32\u0B3F\u0B2A\u0B3F\u0B2C\u0B26\u0B4D\u0B27' : 'Live transcript';
  String get startSpeaking => isOdia ? '\u0B2E\u0B3E\u0B07\u0B15 \u0B1F\u0B3F\u0B2A\u0B3F \u0B30\u0B47\u0B15\u0B30\u0B4D\u0B21 \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Tap the mic to record';
  String get speakYourNews => isOdia ? '\u0B06\u0B2A\u0B23\u0B19\u0B4D\u0B15 \u0B16\u0B2C\u0B30 \u0B13\u0B21\u0B3C\u0B3F\u0B06\u0B30\u0B47 \u0B15\u0B41\u0B39\u0B28\u0B4D\u0B24\u0B41' : 'Your voice will be transcribed to text';
  String get recordHere => isOdia ? '\u0B0F\u0B20\u0B3E\u0B30\u0B47 \u0B30\u0B47\u0B15\u0B30\u0B4D\u0B21 \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Record here';
  String get closeTalkHint => isOdia
      ? '\u0B2D\u0B32 \u0B17\u0B41\u0B23\u0B2C\u0B24\u0B4D\u0B24\u0B3E \u0B2A\u0B3E\u0B07\u0B01 \u0B2B\u0B4B\u0B28 \u0B2E\u0B41\u0B39\u0B01 \u0B2A\u0B3E\u0B16\u0B30\u0B47 \u0B27\u0B30\u0B28\u0B4D\u0B24\u0B41'
      : 'Hold the phone close to your mouth for best results';
  String get moveCloserHint => isOdia
      ? '\u0B2B\u0B4B\u0B28 \u0B2A\u0B3E\u0B16\u0B15\u0B41 \u0B06\u0B23\u0B28\u0B4D\u0B24\u0B41'
      : 'Move closer';
  String get recordingStoppedCall => isOdia
      ? 'ଫୋନ କଲ ପାଇଁ ରେକର୍ଡିଂ ବନ୍ଦ ହେଲା'
      : 'Recording stopped — phone call detected';

  // ===========================================================================
  // Edit actions
  // ===========================================================================
  String get reSpeak => isOdia ? '\u0B2A\u0B41\u0B23\u0B3F \u0B15\u0B41\u0B39\u0B28\u0B4D\u0B24\u0B41' : 'Re-speak';
  String get typeEdit => isOdia ? '\u0B1F\u0B3E\u0B07\u0B2A\u0B4D' : 'Type';
  String get deleteParagraph => isOdia ? '\u0B39\u0B1F\u0B3E\u0B28\u0B4D\u0B24\u0B41' : 'Delete';
  String get addPhotoHere => isOdia ? '\u0B0F\u0B20\u0B3E\u0B30\u0B47 \u0B2B\u0B1F\u0B4B \u0B2F\u0B4B\u0B21\u0B3C\u0B28\u0B4D\u0B24\u0B41' : 'Add photo here';

  // ===========================================================================
  // Details
  // ===========================================================================
  String get headline => isOdia ? '\u0B1F\u0B3E\u0B07\u0B1F\u0B32\u0B4D' : 'Headline';
  String get headlineHint => isOdia ? '\u0B16\u0B2C\u0B30\u0B30 \u0B1F\u0B3E\u0B07\u0B1F\u0B32\u0B4D \u0B32\u0B47\u0B16\u0B28\u0B4D\u0B24\u0B41...' : 'Write the news headline...';
  String get storyBody => isOdia ? '\u0B16\u0B2C\u0B30\u0B30 \u0B2C\u0B3F\u0B2C\u0B30\u0B23\u0B40' : 'Story Body';
  String get storyBodyHint => isOdia ? '\u0B16\u0B2C\u0B30\u0B30 \u0B2C\u0B3F\u0B2C\u0B30\u0B23\u0B40 \u0B32\u0B47\u0B16\u0B28\u0B4D\u0B24\u0B41...' : 'Write the news details...';
  String get category => isOdia ? '\u0B2C\u0B30\u0B4D\u0B17' : 'Category';
  String get categoryFilter => isOdia ? '\u0B36\u0B4D\u0B30\u0B47\u0B23\u0B40' : 'Category';
  String get priority => isOdia ? '\u0B2A\u0B4D\u0B30\u0B3E\u0B25\u0B2E\u0B3F\u0B15\u0B24\u0B3E' : 'Priority';
  String get location => isOdia ? '\u0B38\u0B4D\u0B25\u0B3E\u0B28' : 'Location';
  String get locationHint => isOdia ? '\u0B2F\u0B25\u0B3E: \u0B2D\u0B41\u0B2C\u0B28\u0B47\u0B36\u0B4D\u0B71\u0B30' : 'e.g. Bhubaneswar';

  // Category names
  String get catPolitics => isOdia ? '\u0B30\u0B3E\u0B1C\u0B28\u0B40\u0B24\u0B3F' : 'Politics';
  String get catSports => isOdia ? '\u0B15\u0B4D\u0B30\u0B40\u0B21\u0B3C\u0B3E' : 'Sports';
  String get catCrime => isOdia ? '\u0B05\u0B2A\u0B30\u0B3E\u0B27' : 'Crime';
  String get catBusiness => isOdia ? '\u0B2C\u0B4D\u0B2F\u0B2C\u0B38\u0B3E\u0B5F' : 'Business';
  String get catEntertainment => isOdia ? '\u0B2E\u0B28\u0B4B\u0B30\u0B1E\u0B4D\u0B1C\u0B28' : 'Entertainment';
  String get catEducation => isOdia ? '\u0B36\u0B3F\u0B15\u0B4D\u0B37\u0B3E' : 'Education';
  String get catHealth => isOdia ? '\u0B38\u0B4D\u0B71\u0B3E\u0B38\u0B4D\u0B25\u0B4D\u0B5F' : 'Health';
  String get catTechnology => isOdia ? '\u0B2A\u0B4D\u0B30\u0B2F\u0B41\u0B15\u0B4D\u0B24\u0B3F' : 'Technology';
  String get catDisaster => isOdia ? '\u0B2C\u0B3F\u0B2A\u0B26' : 'Disaster';
  String get catOther => isOdia ? '\u0B05\u0B28\u0B4D\u0B5F\u0B3E\u0B28\u0B4D\u0B5F' : 'Other';

  /// Map category API key to localized label.
  String categoryLabel(String? key) {
    switch (key) {
      case 'politics': return catPolitics;
      case 'sports': return catSports;
      case 'crime': return catCrime;
      case 'business': return catBusiness;
      case 'entertainment': return catEntertainment;
      case 'education': return catEducation;
      case 'health': return catHealth;
      case 'technology': return catTechnology;
      case 'disaster': return catDisaster;
      case 'other': return catOther;
      default: return key ?? all;
    }
  }

  // Priority names
  String get priorityNormal => isOdia ? '\u0B38\u0B3E\u0B27\u0B3E\u0B30\u0B23' : 'Normal';
  String get priorityUrgent => isOdia ? '\u0B1C\u0B30\u0B41\u0B30\u0B40' : 'Urgent';
  String get priorityBreaking => isOdia ? '\u0B2C\u0B4D\u0B30\u0B47\u0B15\u0B3F\u0B02' : 'Breaking';

  // ===========================================================================
  // Media
  // ===========================================================================
  String get photo => isOdia ? '\u0B2B\u0B1F\u0B4B' : 'Photo';
  String get video => isOdia ? '\u0B2D\u0B3F\u0B21\u0B3F\u0B13' : 'Video';
  String get document => isOdia ? '\u0B21\u0B15\u0B41\u0B2E\u0B47\u0B23\u0B4D\u0B1F' : 'Document';

  // ===========================================================================
  // Home Sections
  // ===========================================================================
  String get myDrafts => isOdia ? '\u0B2E\u0B4B \u0B21\u0B4D\u0B30\u0B3E\u0B2B\u0B4D\u0B1F' : 'My Drafts';
  String get submitted => isOdia ? '\u0B26\u0B3E\u0B16\u0B32 \u0B39\u0B4B\u0B07\u0B1B\u0B3F' : 'Submitted';

  // ===========================================================================
  // Empty States
  // ===========================================================================
  String get startFirstStory => isOdia ? '\u0B06\u0B2A\u0B23\u0B19\u0B4D\u0B15 \u0B2A\u0B4D\u0B30\u0B25\u0B2E \u0B16\u0B2C\u0B30 \u0B06\u0B30\u0B2E\u0B4D\u0B2D \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Start your first story';
  String get tapPlusToStart => isOdia ? "'+' \u0B2C\u0B1F\u0B28 \u0B26\u0B2C\u0B3E\u0B07 \u0B15\u0B39\u0B3F\u0B2C\u0B3E \u0B06\u0B30\u0B2E\u0B4D\u0B2D \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41" : "Press '+' to start speaking";
  String get createNewStory => isOdia ? '\u0B28\u0B42\u0B06 \u0B16\u0B2C\u0B30 \u0B24\u0B3F\u0B06\u0B30\u0B3F \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Create a new story';

  // ===========================================================================
  // Submissions Screen
  // ===========================================================================
  String get mySubmissions => isOdia ? '\u0B2E\u0B4B \u0B26\u0B3E\u0B16\u0B32' : 'My Submissions';
  String get tabAll => isOdia ? '\u0B38\u0B2C\u0B41' : 'All';
  String get tabDraft => isOdia ? '\u0B21\u0B4D\u0B30\u0B3E\u0B2B\u0B4D\u0B1F' : 'Draft';
  String get tabSubmitted => isOdia ? '\u0B26\u0B3E\u0B16\u0B32' : 'Submitted';
  String get tabApproved => isOdia ? '\u0B05\u0B28\u0B41\u0B2E\u0B4B\u0B26\u0B3F\u0B24' : 'Approved';
  String get tabRejected => isOdia ? '\u0B2A\u0B4D\u0B30\u0B24\u0B4D\u0B5F\u0B3E\u0B16\u0B4D\u0B5F\u0B3E\u0B24' : 'Rejected';
  String get tabPublished => isOdia ? '\u0B2A\u0B4D\u0B30\u0B15\u0B3E\u0B36\u0B3F\u0B24' : 'Published';
  String get noStoriesYet => isOdia ? '\u0B0F\u0B2A\u0B30\u0B4D\u0B2F\u0B4D\u0B5F\u0B28\u0B4D\u0B24 \u0B15\u0B4C\u0B23\u0B38\u0B3F \u0B16\u0B2C\u0B30 \u0B28\u0B3E\u0B39\u0B3F\u0B01' : 'No stories yet';

  // ===========================================================================
  // Profile Screen
  // ===========================================================================
  String get notifications => isOdia ? '\u0B38\u0B42\u0B1A\u0B28\u0B3E' : 'Notifications';
  String get manageAlerts => isOdia ? '\u0B06\u0B32\u0B30\u0B4D\u0B1F \u0B2A\u0B30\u0B3F\u0B1A\u0B3E\u0B33\u0B28\u0B3E' : 'Manage alerts';
  String get language => isOdia ? '\u0B2D\u0B3E\u0B37\u0B3E' : 'Language';
  String get languageSubtitle => 'English / \u0B13\u0B21\u0B3C\u0B3F\u0B06';
  String get theme => isOdia ? '\u0B25\u0B3F\u0B2E\u0B4D' : 'Theme';
  String get selectTheme => isOdia ? '\u0B25\u0B3F\u0B2E\u0B4D \u0B2C\u0B3E\u0B1B\u0B28\u0B4D\u0B24\u0B41' : 'Select Theme';
  String get helpAndSupport => isOdia ? '\u0B38\u0B3E\u0B39\u0B3E\u0B2F\u0B4D\u0B5F \u0B0F\u0B2C\u0B02 \u0B38\u0B2E\u0B30\u0B4D\u0B25\u0B28' : 'Help & Support';
  String get faqsAndContact => isOdia ? 'FAQ \u0B0F\u0B2C\u0B02 \u0B38\u0B2E\u0B4D\u0B2A\u0B30\u0B4D\u0B15' : 'FAQs and contact';
  String get about => isOdia ? '\u0B2C\u0B3F\u0B37\u0B5F\u0B30\u0B47' : 'About';
  String get logout => isOdia ? '\u0B32\u0B17\u0B06\u0B09\u0B1F' : 'Logout';
  String get signOut => isOdia ? '\u0B06\u0B2A\u0B23\u0B19\u0B4D\u0B15 \u0B06\u0B15\u0B3E\u0B09\u0B23\u0B4D\u0B1F\u0B30\u0B41 \u0B2C\u0B3E\u0B39\u0B3E\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Sign out of your account';
  String get logoutConfirm => isOdia ? '\u0B06\u0B2A\u0B23 \u0B32\u0B17\u0B06\u0B09\u0B1F \u0B15\u0B30\u0B3F\u0B2C\u0B3E\u0B15\u0B41 \u0B1A\u0B3E\u0B39\u0B41\u0B01\u0B1B\u0B28\u0B4D\u0B24\u0B3F?' : 'Are you sure you want to sign out?';
  String get total => isOdia ? '\u0B2E\u0B4B\u0B1F' : 'Total';
  String get approved => isOdia ? '\u0B05\u0B28\u0B41\u0B2E\u0B4B\u0B26\u0B3F\u0B24' : 'Approved';
  String get published => isOdia ? '\u0B2A\u0B4D\u0B30\u0B15\u0B3E\u0B36\u0B3F\u0B24' : 'Published';
  String get comingSoon => isOdia ? '\u0B36\u0B40\u0B18\u0B4D\u0B30 \u0B06\u0B38\u0B41\u0B1B\u0B3F' : 'Coming soon';
  String get privacyPolicy => isOdia ? '\u0B17\u0B4B\u0B2A\u0B28\u0B40\u0B5F\u0B24\u0B3E \u0B28\u0B40\u0B24\u0B3F' : 'Privacy Policy';
  String get privacyPolicySubtitle => isOdia ? '\u0B06\u0B2E\u0B15\u0B41 \u0B2C\u0B4D\u0B30\u0B3E\u0B09\u0B1C\u0B30\u0B30\u0B47 \u0B16\u0B4B\u0B32\u0B28\u0B4D\u0B24\u0B41' : 'Open in browser';
  // Force-update gate
  String get forceUpdateTitle => isOdia ? '\u0B05\u0B2A\u0B21\u0B47\u0B1F \u0B06\u0B2C\u0B36\u0B4D\u0B2F\u0B15' : 'Update required';
  String get forceUpdateBody => isOdia ? '\u0B2C\u0B43\u0B24\u0B4D\u0B24\u0B3E\u0B28\u0B4D\u0B24\u0B30 \u0B0F\u0B15 \u0B28\u0B42\u0B24\u0B28 \u0B38\u0B02\u0B38\u0B4D\u0B15\u0B30\u0B23 \u0B09\u0B2A\u0B32\u0B2C\u0B4D\u0B27\u0964 \u0B05\u0B17\u0B4D\u0B30\u0B38\u0B30 \u0B39\u0B2C\u0B3E \u0B2A\u0B3E\u0B07\u0B01 \u0B05\u0B2D\u0B3F\u0B28\u0B2C \u0B38\u0B02\u0B38\u0B4D\u0B15\u0B30\u0B23\u0B15\u0B41 \u0B05\u0B2A\u0B21\u0B47\u0B1F \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41\u0964' : 'A new version of Vrittant is available. Please update to continue.';
  String get forceUpdateButton => isOdia ? '\u0B0F\u0B2C\u0B47 \u0B05\u0B2A\u0B21\u0B47\u0B1F \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Update now';

  // Mic permission UX
  String get micPermissionTitle => isOdia ? '\u0B2E\u0B3E\u0B07\u0B15\u0B4D\u0B30\u0B4B\u0B2B\u0B4B\u0B28 \u0B05\u0B28\u0B41\u0B2E\u0B24\u0B3F \u0B06\u0B2C\u0B36\u0B4D\u0B2F\u0B15' : 'Microphone access needed';
  String get micPermissionRationale => isOdia ? '\u0B16\u0B2C\u0B30 \u0B36\u0B4D\u0B30\u0B41\u0B24\u0B32\u0B47\u0B16\u0B28 \u0B0F\u0B2C\u0B02 \u0B2D\u0B5F\u0B47\u0B38 \u0B05\u0B28\u0B30\u0B4D\u0B32\u0B2E\u0B47\u0B23\u0B4D\u0B1F \u0B2A\u0B3E\u0B07\u0B01 \u0B2C\u0B43\u0B24\u0B4D\u0B24\u0B3E\u0B28\u0B4D\u0B24\u0B15\u0B41 \u0B2E\u0B3E\u0B07\u0B15\u0B4D\u0B30\u0B4B\u0B2B\u0B4B\u0B28\u0B30 \u0B06\u0B2C\u0B36\u0B4D\u0B2F\u0B15\u0964' : 'Vrittant needs microphone access to dictate stories and enrol your voice.';
  String get micPermissionAllow => isOdia ? '\u0B05\u0B28\u0B41\u0B2E\u0B24\u0B3F \u0B26\u0B3F\u0B05\u0B28\u0B4D\u0B24\u0B41' : 'Allow';
  String get micPermissionBlockedTitle => isOdia ? '\u0B2E\u0B3E\u0B07\u0B15\u0B4D\u0B30\u0B4B\u0B2B\u0B4B\u0B28 \u0B05\u0B26\u0B4D\u0B5F\u0B3E\u0B2A\u0B3F \u0B05\u0B28\u0B41\u0B2E\u0B24\u0B3F \u0B28\u0B3E\u0B39\u0B3F\u0B01' : 'Microphone is blocked';
  String get micPermissionBlockedBody => isOdia ? '\u0B06\u0B2A\u0B23 \u0B2E\u0B3E\u0B07\u0B15\u0B4D\u0B30\u0B4B\u0B2B\u0B4B\u0B28 \u0B05\u0B28\u0B41\u0B2E\u0B24\u0B3F \u0B05\u0B38\u0B4D\u0B35\u0B40\u0B15\u0B3E\u0B30 \u0B15\u0B30\u0B3F\u0B26\u0B47\u0B07\u0B1B\u0B28\u0B4D\u0B24\u0B3F\u0964 \u0B27\u0B4D\u0B35\u0B28\u0B3F \u0B2A\u0B41\u0B28\u0B30\u0B41\u0B26\u0B4D\u0B27\u0B3E\u0B30 \u0B15\u0B30\u0B3F\u0B2C\u0B3E\u0B15\u0B41 \u0B38\u0B47\u0B1F\u0B3F\u0B02\u0B38\u0B15\u0B41 \u0B2F\u0B3E\u0B06\u0B28\u0B4D\u0B24\u0B41\u0964' : 'You previously denied microphone access. To dictate again, enable it in Settings.';
  String get micPermissionRestricted => isOdia ? '\u0B2E\u0B3E\u0B07\u0B15\u0B4D\u0B30\u0B4B\u0B2B\u0B4B\u0B28 \u0B0F\u0B07 \u0B21\u0B3F\u0B2D\u0B3E\u0B07\u0B38\u0B30\u0B47 \u0B28\u0B3F\u0B5F\u0B28\u0B4D\u0B24\u0B4D\u0B30\u0B3F\u0B24 \u0B05\u0B1F\u0B15\u0B3E \u0B2F\u0B3E\u0B07\u0B1B\u0B3F\u0964' : 'Microphone access is restricted on this device.';
  String get openSettings => isOdia ? '\u0B38\u0B47\u0B1F\u0B3F\u0B02\u0B38 \u0B16\u0B4B\u0B32\u0B28\u0B4D\u0B24\u0B41' : 'Open Settings';
  String get notNow => isOdia ? '\u0B0F\u0B2A\u0B30\u0B3F \u0B28\u0B41\u0B39\u0B47\u0B01' : 'Not now';
  String get couldNotOpenLink => isOdia ? '\u0B32\u0B3F\u0B19\u0B4D\u0B15 \u0B16\u0B4B\u0B32\u0B3F \u0B39\u0B47\u0B32\u0B3E\u0B28\u0B3E\u0B39\u0B3F\u0B01' : 'Could not open link';
  String get couldNotOpenFile => isOdia ? '\u0B2B\u0B3E\u0B07\u0B32 \u0B16\u0B4B\u0B32\u0B3F \u0B39\u0B47\u0B32\u0B3E\u0B28\u0B3E\u0B39\u0B3F\u0B01' : 'Could not open file';
  String get downloadFailed => isOdia ? '\u0B21\u0B3E\u0B09\u0B28\u0B32\u0B4B\u0B21\u0B4D \u0B05\u0B38\u0B2B\u0B33 \u0B39\u0B47\u0B32\u0B3E' : 'Download failed';
  String get appDescription => isOdia ? '\u0B2C\u0B43\u0B24\u0B4D\u0B24\u0B3E\u0B28\u0B4D\u0B24 \u0B39\u0B47\u0B09\u0B1B\u0B3F \u0B0F\u0B15 \u0B38\u0B4D\u0B2E\u0B3E\u0B30\u0B4D\u0B1F \u0B28\u0B4D\u0B5F\u0B41\u0B1C\u0B4D \u0B30\u0B3F\u0B2A\u0B4B\u0B30\u0B4D\u0B1F\u0B3F\u0B02 \u0B1F\u0B41\u0B32\u0B4D \u0B2F\u0B3E\u0B39\u0B3E \u0B38\u0B3E\u0B2E\u0B4D\u0B2C\u0B3E\u0B26\u0B3F\u0B15\u0B2E\u0B3E\u0B28\u0B19\u0B4D\u0B15\u0B41 \u0B16\u0B2C\u0B30 \u0B38\u0B02\u0B17\u0B4D\u0B30\u0B39, \u0B38\u0B2E\u0B4D\u0B2A\u0B3E\u0B26\u0B28\u0B3E \u0B0F\u0B2C\u0B02 \u0B2A\u0B4D\u0B30\u0B15\u0B3E\u0B36\u0B28\u0B3E\u0B30\u0B47 \u0B38\u0B3E\u0B39\u0B3E\u0B2F\u0B4D\u0B5F \u0B15\u0B30\u0B47\u0964' : 'A smart news reporting tool that helps journalists with news gathering, editing, and publishing.';

  // ===========================================================================
  // All News Screen
  // ===========================================================================
  String get today => isOdia ? '\u0B06\u0B1C\u0B3F' : 'Today';
  String get yesterday => isOdia ? '\u0B17\u0B24\u0B15\u0B3E\u0B32\u0B3F' : 'Yesterday';
  String get statusFilter => isOdia ? '\u0B38\u0B4D\u0B25\u0B3F\u0B24\u0B3F' : 'Status';
  String get dateRange => isOdia ? '\u0B24\u0B3E\u0B30\u0B3F\u0B16 \u0B2A\u0B30\u0B3F\u0B27\u0B3F' : 'Date range';
  String get dateFrom => isOdia ? '\u0B06\u0B30\u0B2E\u0B4D\u0B2D' : 'From';
  String get dateTo => isOdia ? '\u0B36\u0B47\u0B37' : 'To';
  String get clearAll => isOdia ? '\u0B38\u0B2C\u0B41 \u0B38\u0B2B\u0B3E \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Clear all';
  String get noNewsFound => isOdia ? '\u0B15\u0B3F\u0B1B\u0B3F \u0B16\u0B2C\u0B30 \u0B2E\u0B3F\u0B33\u0B3F\u0B32\u0B3E \u0B28\u0B3E\u0B39\u0B3F\u0B01' : 'No news found';
  String get voiceSearchUnavailable => isOdia ? '\u0B2D\u0B0F\u0B38\u0B4D \u0B38\u0B30\u0B4D\u0B1A\u0B4D \u0B09\u0B2A\u0B32\u0B2C\u0B4D\u0B27 \u0B28\u0B3E\u0B39\u0B3F\u0B01' : 'Voice search unavailable';

  // ===========================================================================
  // Login Screen
  // ===========================================================================
  String get sendOtp => isOdia ? 'OTP \u0B2A\u0B20\u0B3E\u0B28\u0B4D\u0B24\u0B41' : 'SEND OTP';
  String get verifyPhone => isOdia ? '\u0B2B\u0B4B\u0B28 \u0B2F\u0B3E\u0B1E\u0B4D\u0B1A' : 'Verify Phone';
  String get enterCodeSent => isOdia ? '\u0B2A\u0B20\u0B3E\u0B2F\u0B3F\u0B25\u0B3F\u0B2C\u0B3E \u0B15\u0B4B\u0B21\u0B4D \u0B2A\u0B4D\u0B30\u0B2C\u0B47\u0B36 \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41 ' : 'Enter the code sent to ';
  String get editNumber => isOdia ? '\u0B28\u0B2E\u0B4D\u0B2C\u0B30 \u0B2C\u0B26\u0B33\u0B3E\u0B28\u0B4D\u0B24\u0B41' : 'Edit Number';
  String get resendCode => isOdia ? '\u0B2A\u0B41\u0B23\u0B3F \u0B2A\u0B20\u0B3E\u0B28\u0B4D\u0B24\u0B41' : 'Resend Code';
  String get verifyAndContinue => isOdia ? '\u0B2F\u0B3E\u0B1E\u0B4D\u0B1A \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Verify & Continue';
  String get phoneNumber => isOdia ? '\u0B2B\u0B4B\u0B28 \u0B28\u0B2E\u0B4D\u0B2C\u0B30' : 'PHONE NUMBER';
  String get termsAgree => isOdia ? '\u0B06\u0B17\u0B15\u0B41 \u0B2C\u0B22\u0B3F\u0B2C\u0B3E \u0B26\u0B4D\u0B71\u0B3E\u0B30\u0B3E \u0B06\u0B2A\u0B23 \u0B06\u0B2E\u0B30 ' : 'By continuing, you agree to our ';
  String get termsOfService => isOdia ? '\u0B38\u0B47\u0B2C\u0B3E \u0B36\u0B30\u0B4D\u0B24\u0B3E\u0B2C\u0B33\u0B40' : 'Terms of Service';

  // ===========================================================================
  // Files Screen
  // ===========================================================================
  String get filesTabAll => isOdia ? '\u0B38\u0B2C\u0B41' : 'All';
  String get filesTabRecent => isOdia ? '\u0B38\u0B3E\u0B2E\u0B4D\u0B2A\u0B4D\u0B30\u0B24\u0B3F\u0B15' : 'Recent';
  String get filesTabGrouped => isOdia ? '\u0B17\u0B4B\u0B37\u0B4D\u0B20\u0B40\u0B2C\u0B26\u0B4D\u0B27' : 'Grouped';
  String get filesTabStarred => isOdia ? '\u0B24\u0B3E\u0B30\u0B3E\u0B19\u0B4D\u0B15\u0B3F\u0B24' : 'Starred';
  String get noFilesYet => isOdia ? '\u0B0F\u0B2A\u0B30\u0B4D\u0B2F\u0B4D\u0B5F\u0B28\u0B4D\u0B24 \u0B15\u0B4C\u0B23\u0B38\u0B3F \u0B2B\u0B3E\u0B07\u0B32 \u0B28\u0B3E\u0B39\u0B3F\u0B01' : 'No Files Yet';
  String get noFilesDesc => isOdia ? '\u0B06\u0B2A\u0B23\u0B19\u0B4D\u0B15 \u0B16\u0B2C\u0B30\u0B30 \u0B38\u0B02\u0B32\u0B17\u0B4D\u0B28 \u0B0F\u0B20\u0B3E\u0B30\u0B47 \u0B26\u0B47\u0B16\u0B3E\u0B2F\u0B3F\u0B2C' : 'Attachments from your stories will appear here grouped by type';
  String get noFilesAllDesc => isOdia ? '\u0B06\u0B2A\u0B23\u0B19\u0B4D\u0B15 \u0B16\u0B2C\u0B30\u0B30 \u0B38\u0B02\u0B32\u0B17\u0B4D\u0B28 \u0B0F\u0B20\u0B3E\u0B30\u0B47 \u0B26\u0B47\u0B16\u0B3E\u0B2F\u0B3F\u0B2C' : 'Attachments from your stories will appear here';
  String get voiceNotes => isOdia ? '\u0B2D\u0B0F\u0B38\u0B4D \u0B28\u0B4B\u0B1F\u0B4D' : 'Voice Notes';
  String get aiSorted => isOdia ? 'AI \u0B38\u0B1C\u0B4D\u0B1C\u0B3F\u0B24' : 'AI SORTED';
  String get scenePhotos => isOdia ? '\u0B26\u0B43\u0B36\u0B4D\u0B5F \u0B2B\u0B1F\u0B4B' : 'Scene Photos';
  String get viewAll => isOdia ? '\u0B38\u0B2C\u0B41 \u0B26\u0B47\u0B16\u0B28\u0B4D\u0B24\u0B41' : 'View All';
  String get documents => isOdia ? '\u0B28\u0B25\u0B3F\u0B2A\u0B24\u0B4D\u0B30' : 'Documents';
  String get noRecentFiles => isOdia ? '\u0B38\u0B3E\u0B2E\u0B4D\u0B2A\u0B4D\u0B30\u0B24\u0B3F\u0B15 \u0B2B\u0B3E\u0B07\u0B32 \u0B28\u0B3E\u0B39\u0B3F\u0B01' : 'No Recent Files';
  String get noRecentFilesDesc => isOdia ? '\u0B38\u0B3E\u0B2E\u0B4D\u0B2A\u0B4D\u0B30\u0B24\u0B3F\u0B15 \u0B2B\u0B3E\u0B07\u0B32 \u0B0F\u0B20\u0B3E\u0B30\u0B47 \u0B26\u0B47\u0B16\u0B3E\u0B2F\u0B3F\u0B2C' : 'Recently accessed files appear here';
  String get starredFiles => isOdia ? '\u0B24\u0B3E\u0B30\u0B3E\u0B19\u0B4D\u0B15\u0B3F\u0B24 \u0B2B\u0B3E\u0B07\u0B32' : 'Starred Files';
  String get starredFilesDesc => isOdia ? '\u0B06\u0B2A\u0B23 \u0B24\u0B3E\u0B30\u0B3E\u0B19\u0B4D\u0B15\u0B3F\u0B24 \u0B2B\u0B3E\u0B07\u0B32 \u0B0F\u0B20\u0B3E\u0B30\u0B47 \u0B26\u0B47\u0B16\u0B3E\u0B2F\u0B3F\u0B2C' : 'Files you star will appear here';
  String get untitled => isOdia ? '\u0B36\u0B40\u0B30\u0B4D\u0B37\u0B15\u0B2C\u0B3F\u0B39\u0B40\u0B28' : 'Untitled';

  // ===========================================================================
  // News Card — Status & Priority badges
  // ===========================================================================
  String get statusDraft => isOdia ? '\u0B21\u0B4D\u0B30\u0B3E\u0B2B\u0B4D\u0B1F' : 'Draft';
  String get statusSubmitted => isOdia ? '\u0B26\u0B3E\u0B16\u0B32' : 'Submitted';
  String get statusApproved => isOdia ? '\u0B05\u0B28\u0B41\u0B2E\u0B4B\u0B26\u0B3F\u0B24' : 'Approved';
  String get statusRejected => isOdia ? '\u0B2A\u0B4D\u0B30\u0B24\u0B4D\u0B5F\u0B3E\u0B16\u0B4D\u0B5F\u0B3E\u0B24' : 'Rejected';
  String get statusPublished => isOdia ? '\u0B2A\u0B4D\u0B30\u0B15\u0B3E\u0B36\u0B3F\u0B24' : 'Published';
  String get badgeBreaking => isOdia ? '\u0B2C\u0B4D\u0B30\u0B47\u0B15\u0B3F\u0B02' : 'BREAKING';
  String get badgeUrgent => isOdia ? '\u0B1C\u0B30\u0B41\u0B30\u0B40' : 'URGENT';
  String timeAgoMinutes(int n) => isOdia ? '$n \u0B2E\u0B3F\u0B28\u0B3F\u0B1F \u0B2A\u0B42\u0B30\u0B4D\u0B2C\u0B47' : '${n}m ago';
  String timeAgoHours(int n) => isOdia ? '$n \u0B18\u0B23\u0B4D\u0B1F\u0B3E \u0B2A\u0B42\u0B30\u0B4D\u0B2C\u0B47' : '${n}h ago';
  String timeAgoDays(int n) => isOdia ? '$n \u0B26\u0B3F\u0B28 \u0B2A\u0B42\u0B30\u0B4D\u0B2C\u0B47' : '${n}d ago';
  String filesAttached(int n) => isOdia ? '$n \u0B1F\u0B3F \u0B2B\u0B3E\u0B07\u0B32 \u0B38\u0B02\u0B32\u0B17\u0B4D\u0B28' : '$n file(s) attached';

  /// Map status label used in All News filter.
  String statusLabel(String? key) {
    switch (key) {
      case 'draft': return statusDraft;
      case 'submitted': return statusSubmitted;
      default: return all;
    }
  }


  // ===========================================================================
  // Voice Enrollment
  // ===========================================================================
  String get voiceEnrollment => isOdia ? '\u0B38\u0B4D\u0B2C\u0B30 \u0B28\u0B3F\u0B2C\u0B28\u0B4D\u0B27\u0B28' : 'Voice Enrollment';
  String get voiceEnrollmentDesc => isOdia ? '\u0B06\u0B2A\u0B23\u0B19\u0B4D\u0B15 \u0B38\u0B4D\u0B2C\u0B30 \u0B1A\u0B3F\u0B39\u0B4D\u0B28\u0B1F \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Register your voice';
  String get enrollYourVoice => isOdia ? '\u0B06\u0B2A\u0B23\u0B19\u0B4D\u0B15 \u0B38\u0B4D\u0B2C\u0B30 \u0B28\u0B3F\u0B2C\u0B28\u0B4D\u0B27\u0B28 \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Enroll Your Voice';
  String get enrollDescription => isOdia
      ? '\u0B06\u0B2A\u0B23\u0B19\u0B4D\u0B15 \u0B38\u0B4D\u0B2C\u0B30 \u0B1A\u0B3F\u0B39\u0B4D\u0B28\u0B1F \u0B2A\u0B3E\u0B07\u0B01 \u0B69 \u0B1F\u0B3F \u0B28\u0B2E\u0B41\u0B28\u0B3E \u0B30\u0B47\u0B15\u0B30\u0B4D\u0B21\u0B4D \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41\u0964 \u0B0F\u0B39\u0B3E \u0B2A\u0B30\u0B47 \u0B15\u0B47\u0B2C\u0B33 \u0B06\u0B2A\u0B23\u0B19\u0B4D\u0B15 \u0B38\u0B4D\u0B2C\u0B30 \u0B32\u0B3F\u0B2A\u0B3F\u0B2C\u0B26\u0B4D\u0B27 \u0B39\u0B47\u0B2C\u0964'
      : 'Record 3 voice samples to register your voice. After this, only your voice will be transcribed.';
  String get recordSample => isOdia ? '\u0B28\u0B2E\u0B41\u0B28\u0B3E' : 'Sample';
  String get recordInstruction => isOdia
      ? '\u0B36\u0B3E\u0B28\u0B4D\u0B24 \u0B1C\u0B3E\u0B17\u0B3E\u0B30\u0B47 \u0B68-\u0B67\u0B66 \u0B38\u0B47\u0B15\u0B47\u0B23\u0B4D\u0B21 \u0B2A\u0B3E\u0B07\u0B01 \u0B38\u0B4D\u0B2C\u0B3E\u0B2D\u0B3E\u0B2C\u0B3F\u0B15 \u0B2D\u0B3E\u0B2C\u0B30\u0B47 \u0B15\u0B25\u0B3E \u0B15\u0B39\u0B28\u0B4D\u0B24\u0B41'
      : 'Speak naturally for 5-10 seconds in a quiet place';
  String get sample => isOdia ? '\u0B28\u0B2E\u0B41\u0B28\u0B3E' : 'Sample';
  String get secondsShort => isOdia ? '\u0B38\u0B47' : 's';
  String get voiceEnrolled => isOdia ? '\u0B38\u0B4D\u0B2C\u0B30 \u0B28\u0B3F\u0B2C\u0B28\u0B4D\u0B27\u0B3F\u0B24 \u0B39\u0B47\u0B32\u0B3E!' : 'Voice Enrolled!';
  String get samplesRecorded => isOdia ? '\u0B1F\u0B3F \u0B28\u0B2E\u0B41\u0B28\u0B3E \u0B30\u0B47\u0B15\u0B30\u0B4D\u0B21\u0B4D \u0B39\u0B47\u0B32\u0B3E' : 'samples recorded';
  String get testYourVoice => isOdia ? '\u0B38\u0B4D\u0B2C\u0B30 \u0B2A\u0B30\u0B40\u0B15\u0B4D\u0B37\u0B3E' : 'Test Your Voice';
  String get testDescription => isOdia
      ? '\u0B06\u0B2A\u0B23\u0B19\u0B4D\u0B15 \u0B38\u0B4D\u0B2C\u0B30 \u0B1A\u0B3F\u0B39\u0B4D\u0B28\u0B1F \u0B39\u0B47\u0B09\u0B1B\u0B3F \u0B15\u0B3F \u0B28\u0B3E\u0B39\u0B3F\u0B01 \u0B2A\u0B30\u0B40\u0B15\u0B4D\u0B37\u0B3E \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41'
      : 'Test if your voice is recognized correctly';
  String get voiceVerified => isOdia ? '\u0B38\u0B4D\u0B2C\u0B30 \u0B1A\u0B3F\u0B39\u0B4D\u0B28\u0B3F\u0B24 \u0B39\u0B47\u0B32\u0B3E!' : 'Voice verified!';
  String get voiceNotRecognized => isOdia ? '\u0B38\u0B4D\u0B2C\u0B30 \u0B1A\u0B3F\u0B39\u0B4D\u0B28\u0B3F\u0B24 \u0B39\u0B47\u0B32\u0B3E \u0B28\u0B3E\u0B39\u0B3F\u0B01' : 'Voice not recognized';
  String get matchScore => isOdia ? '\u0B2E\u0B3F\u0B33\u0B28 \u0B38\u0B4D\u0B15\u0B4B\u0B30' : 'Match score';
  String get reEnroll => isOdia ? '\u0B2A\u0B41\u0B23\u0B3F \u0B28\u0B3F\u0B2C\u0B28\u0B4D\u0B27\u0B28 \u0B15\u0B30\u0B28\u0B4D\u0B24\u0B41' : 'Re-enroll Voice';
  String get speakerVerified => isOdia ? '\u0B38\u0B4D\u0B2C\u0B30 \u0B2F\u0B3E\u0B1E\u0B4D\u0B1A\u0B3F\u0B24' : 'Speaker verified';
  String get otherVoiceDetected => isOdia ? '\u0B05\u0B28\u0B4D\u0B5F \u0B38\u0B4D\u0B2C\u0B30 \u0B1A\u0B3F\u0B39\u0B4D\u0B28\u0B3F\u0B24' : 'Other voice detected';
  String get enrolled => isOdia ? '\u0B28\u0B3F\u0B2C\u0B28\u0B4D\u0B27\u0B3F\u0B24' : 'Enrolled';
  String get notEnrolled => isOdia ? '\u0B28\u0B3F\u0B2C\u0B28\u0B4D\u0B27\u0B3F\u0B24 \u0B28\u0B3E\u0B39\u0B3F\u0B01' : 'Not enrolled';

  // ===========================================================================
  // Notepad — attach menu, status, file types, AI instruction
  // ===========================================================================
  String get instructionNotHeard => isOdia
      ? 'ନିର୍ଦ୍ଦେଶ ଶୁଣାଗଲା ନାହିଁ। ଦୟାକରି ପୁଣି ଚେଷ୍ଟା କରନ୍ତୁ।'
      : 'Instruction not heard. Please try again.';
  String get attachFile => isOdia ? 'ଫାଇଲ ଯୋଡ଼ନ୍ତୁ' : 'Attach file';
  String get camera => isOdia ? 'କ୍ୟାମେରା' : 'Camera';
  String get takeAPhoto => isOdia ? 'ଫଟୋ ତୁଳନ୍ତୁ' : 'Take a photo';
  String get gallery => isOdia ? 'ଗ୍ୟାଲେରୀ' : 'Gallery';
  String get pickAPhoto => isOdia ? 'ଫଟୋ ବାଛନ୍ତୁ' : 'Pick a photo';
  String get recordHereSubtitle => isOdia ? 'ଏଠି ସ୍ୱର ଅନୁଚ୍ଛେଦ ଯୋଗ କରନ୍ତୁ' : 'Add a voice paragraph here';
  String get attachPhoto => isOdia ? 'ଫଟୋ ଯୋଡ଼ନ୍ତୁ' : 'Attach photo';
  String get takeOrPickPhoto => isOdia ? 'ଫଟୋ ତୁଳନ୍ତୁ ବା ବାଛନ୍ତୁ' : 'Take or pick photo';
  String get attachDocument => isOdia ? 'ନଥିପତ୍ର ଯୋଡ଼ନ୍ତୁ' : 'Attach document';
  String get deleteDraft => isOdia ? 'ଡ୍ରାଫ୍ଟ ହଟାନ୍ତୁ' : 'Delete draft';

  /// Warning line in the delete confirmation dialog. Drafts don't go
  /// to a trash — once deleted they are gone, including any locally-
  /// queued audio backups. Make that explicit so reporters don't tap
  /// through on muscle memory.
  String get deleteDraftWarning => isOdia
      ? 'ଏହା ସ୍ଥାୟୀ ଭାବେ ହଟିଯିବ। ଫେରସ୍ତ ଆଣିହେବ ନାହିଁ।'
      : 'This will be permanently removed. Cannot be undone.';

  /// Pluralized "N paragraphs" subtitle in the delete dialog so the
  /// reporter knows the size of what they're about to lose. The
  /// pluralization uses Odia's invariant noun form (same word for
  /// singular and plural) so we avoid the singular/plural fork.
  String draftParagraphCount(int n) => isOdia
      ? '$n ଅନୁଚ୍ଛେଦ'
      : (n == 1 ? '1 paragraph' : '$n paragraphs');

  /// Footer line shown at the end of a paginated story list when the
  /// server has confirmed no more pages. Communicates "you've reached
  /// the bottom" so the reporter doesn't keep scrolling expecting
  /// more.
  String get endOfStories => isOdia
      ? '— ସମସ୍ତ ଖବର ଦେଖାଯାଇଛି —'
      : '— end of stories —';
  String get titleHintWrite => isOdia ? 'ଟାଇଟଲ୍ ଲେଖନ୍ତୁ...' : 'Write the title...';
  String get titleHintSpeak => isOdia ? 'ଟାଇଟଲ୍ କୁହନ୍ତୁ...' : 'Speak the title...';
  String get statusReview => isOdia ? 'ସମୀକ୍ଷା' : 'Review';
  String get directDictation => isOdia ? 'ସିଧା ଲିପିବଦ୍ଧ' : 'Direct typing';
  String get audioLabel => isOdia ? 'ଅଡିଓ' : 'Audio';
  String get fileLabel => isOdia ? 'ଫାଇଲ' : 'File';
  String get enlarge => isOdia ? 'ବଡ଼ କରନ୍ତୁ' : 'Enlarge';
  String get aiInstructHint => isOdia ? 'କି କରିବାକୁ କୁହନ୍ତୁ...' : 'What should I do...';
  String get apply => isOdia ? 'ପ୍ରୟୋଗ କରନ୍ତୁ' : 'Apply';
  String get retranscribe => isOdia ? 'ପୁନଃ ଲିପିଅନ୍ତର କରନ୍ତୁ' : 'Retry transcription';
  String get retranscribing => isOdia ? 'ଲିପିଅନ୍ତର ଚାଲିଛି...' : 'Transcribing...';
  String get editParagraph => isOdia ? 'ସମ୍ପାଦନ କରନ୍ତୁ' : 'Edit';
  String get insertHere => isOdia ? 'ଏଠି ଯୋଗ କରନ୍ତୁ' : 'Insert here';
  String get recordVoice => isOdia ? 'ସ୍ୱର ରେକର୍ଡ କରନ୍ତୁ' : 'Record voice';
  String get typeText => isOdia ? 'ଲେଖନ୍ତୁ' : 'Type';
  String get aiPolish => isOdia ? 'AI ସୁଧାର' : 'AI polish';
  String get tooltipAttach => isOdia ? 'ସଂଲଗ୍ନ' : 'Attach';
  String get tooltipPhoto => isOdia ? 'ଫଟୋ' : 'Photo';
  String get tooltipDoc => isOdia ? 'ନଥିପତ୍ର' : 'Document';
  String get tooltipUndo => isOdia ? 'ପଛକୁ' : 'Undo';
  String get tooltipRedo => isOdia ? 'ଆଗକୁ' : 'Redo';
  String get tooltipBack => isOdia ? 'ପଛକୁ ଯାଆନ୍ତୁ' : 'Back';
  String get tooltipMic => isOdia ? 'ଚାପି ଧରନ୍ତୁ' : 'Hold to record';
  String get tooltipKeyboard => isOdia ? 'ଲେଖି ଯୋଗ କରନ୍ତୁ' : 'Type to add';
  String get tooltipAI => isOdia ? 'AI ସୁଧାର' : 'AI assist';
  String get tooltipClose => isOdia ? 'ବନ୍ଦ କରନ୍ତୁ' : 'Close';
  // "AI Refine" replaces "Generate Story" — same backend call, but the
  // verb communicates what actually happens: clean up the dictation
  // (English slips → Odia script, dedupe phrases, fix punctuation,
  // tighten paragraphs). "Generate" misled reporters into thinking it
  // would invent content, which made them hesitant to use it.
  String get generateStory => isOdia ? 'AI ସଂଶୋଧନ' : 'AI Refine';
  String get generatingStory => isOdia ? 'ସଂଶୋଧନ ହେଉଛି…' : 'Refining…';
  String get aiRefineHint => isOdia
      ? 'ଓଡ଼ିଆ ଲିପିରେ ସଠିକ୍, ଡୁପ୍ଲିକେଟ୍ ସଫା'
      : 'Clean Odia, dedupe & polish';
  /// Tooltip on the disabled AI Refine button — shown when the
  /// reporter just refined and hasn't changed anything since.
  /// Re-enables the moment they edit any paragraph.
  String get aiRefineNoChangesHint => isOdia
      ? 'ସଂଶୋଧନ ପରେ କିଛି ବଦଳ କରିନାହାଁନ୍ତି'
      : 'No changes since last refine';

  /// Tooltip when the reporter has typed too little for AI Refine
  /// to do anything useful (under 20 words). The hint nudges them
  /// to keep going rather than asking the LLM to polish a stub.
  String get aiRefineTooShortHint => isOdia
      ? 'ଅଧିକ ଲେଖନ୍ତୁ — କମ୍ ଶବ୍ଦରେ ସଂଶୋଧନ ଦରକାର ନୁହେଁ'
      : 'Add more text — refine needs a paragraph or so';

  /// Snackbar shown when recording auto-stopped at the 10-minute
  /// hard cap. The "tap mic to continue" hint is critical: reporters
  /// keep dictating with eyes closed; without telling them how to
  /// resume, they think the app died and stop trusting it.
  String get recordingAutoStoppedMaxDuration => isOdia
      ? '୧୦ ମିନିଟ୍ ସମୟ ସମାପ୍ତ। ଚାଲୁ ରଖିବାକୁ ମାଇକ୍ ଚାପନ୍ତୁ।'
      : 'Recording stopped — 10 minute limit reached. Tap mic to continue.';

  /// Snackbar shown when recording auto-stopped because no transcript
  /// arrived for 10 minutes (silence safety net — usually a wedged
  /// websocket).
  String get recordingAutoStoppedSilence => isOdia
      ? 'ଶବ୍ଦ ସୁନାଗଲାନାହିଁ। ମାଇକ୍ ବନ୍ଦ ହୋଇଛି।'
      : 'Recording stopped — no speech detected for 10 minutes.';

  /// Countdown chip shown in the last 60 seconds before the auto-stop
  /// fires. e.g. "0:42 left" / "୦:୪୨ ବାକି". [secondsLeft] is the
  /// integer count of seconds remaining (1..60).
  String recordingTimeLeft(int secondsLeft) {
    final m = secondsLeft ~/ 60;
    final s = secondsLeft.remainder(60).toString().padLeft(2, '0');
    final base = '$m:$s';
    return isOdia ? '${_toOdiaDigits(base)} ବାକି' : '$base left';
  }

  /// Tiny helper for the countdown chip — converts ASCII digits to
  /// Odia digits inline. We don't want to pull in the toOdiaDigits
  /// import here, the logic is one line.
  String _toOdiaDigits(String s) {
    const map = {
      '0': '୦', '1': '୧', '2': '୨', '3': '୩', '4': '୪',
      '5': '୫', '6': '୬', '7': '୭', '8': '୮', '9': '୯',
    };
    return s.split('').map((c) => map[c] ?? c).join();
  }
  String get userNotes => isOdia ? 'ଉପଯୋଗକର୍ତ୍ତା ଟିପ୍ପଣୀ' : 'User Notes';
  String get processingDontLeave => isOdia
      ? 'ପ୍ରକ୍ରିୟାକରଣ ଚାଲିଛି। ବାହାରକୁ ଗଲେ ବି ସୁରକ୍ଷିତ ରହିବ।'
      : 'Processing in progress. Your story will be safe if you leave.';
  String get keepInBackground => isOdia ? 'ପୃଷ୍ଠଭୂମିରେ ରଖନ୍ତୁ' : 'Keep in background';
  String get stayHere => isOdia ? 'ଏଠି ରୁହନ୍ତୁ' : 'Stay here';

  // ===========================================================================
  // Errors (user-facing)
  // ===========================================================================
  String get aiPolishFailed => isOdia ? 'AI ସୁଧାର ବିଫଳ' : 'AI polish failed';
  String get aiInstructionFailed => isOdia ? 'AI ନିର୍ଦ୍ଦେଶ ବିଫଳ' : 'AI instruction failed';
  String get fileUploadFailed => isOdia ? 'ଫାଇଲ ଅପଲୋଡ ବିଫଳ ହେଲା। ପୁଣି ଚେଷ୍ଟା କରନ୍ତୁ।' : 'File upload failed. Please try again.';
  String get fileAttachFailed => isOdia ? 'ଫାଇଲ ଯୋଡ଼ିବା ବିଫଳ ହେଲା' : 'File attach failed';
}
