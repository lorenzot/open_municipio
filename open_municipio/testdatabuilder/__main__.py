from django.core.files import File
from django.conf import settings

from open_municipio.testdatabuilder import conf
from open_municipio.people.models import Institution, Person, GroupCharge
from open_municipio.acts.models import  Act, ActSupport, Attach, Deliberation, Interrogation
from open_municipio.taxonomy.models import Category, Tag

try:
    import json
except ImportError:
    import simplejson as json

import random, os, sys, datetime, lipsum
from rst2pdf.createpdf import RstToPdf




class RandomItemsFactory(object):
    """
    This class is basically a collection of routines allowing automatic generation
    of a random dataset, that may be used to setup a realistic[*]_ testing enviroment
    for the *OpenMunicipio* web application.
    
    .. [*]: At least, this is the intended goal ;-)
    """
    
    APP_ROOT = os.path.abspath(os.path.dirname(__file__))
    
    def create_acts(self):
        """
        Create a bunch of acts. 
        """
        # cleanup
        Act.objects.all().delete()

        election_date = '2010-06-14'

        g = lipsum.Generator()

        #
        # creazione proposte di delibera di consiglio
        #
        institution = Institution.objects.get(slug='consiglio-comunale')

        for i in range(1, 20):
            d = Deliberation(
                idnum="%s" % i,
                title=g.generate_sentence(),
                text=g.generate_paragraph(),
                presentation_date=datetime.date.today() - datetime.timedelta(days=random.randint(1, 10)),
                emitting_institution=institution,
                initiative=Deliberation.COUNSELOR_INIT,
                )
            d.save()
            print "Delibera %s - %s creata" % (d.idnum, d.title)

            nf = random.randint(1, 3)
            nc = random.randint(0, 5)
            print "Aggiunta di %s primi firmatari"  % nf
            maj = random.choice([1, 1, 1, 1, 1, 1, 1, 1, 0]) # first-signers and co-signers come from maj 90% of the times
            presenters = self.get_institution_charges(majority=maj, n=(nf+nc))

            for presenter in presenters[0:nf]:
                act_support = ActSupport(
                    charge=presenter, act=d,
                    support_type=ActSupport.SUPPORT_TYPE.first_signer,
                    support_date=d.presentation_date
                )
                print "%s" % presenter
                act_support.save()

            print "Aggiunta di %s co firmatari"  % nc
            for presenter in presenters[nf:]:
                act_support = ActSupport(
                    charge=presenter, act=d,
                    support_type=ActSupport.SUPPORT_TYPE.co_signer,
                    support_date=d.presentation_date
                )
                print "%s" % presenter
                act_support.save()

            na = random.randint(0, 5)
            print "Aggiunta di %s allegati" % na
            self.generate_random_act_attach(d, n=na)


        for i in range(1, 10):
            a = Interrogation(
                idnum="%s" % i,
                title=g.generate_sentence(),
                text=g.generate_paragraph(),
                presentation_date=datetime.date.today() - datetime.timedelta(days=random.randint(1, 10)),
                answer_type=random.choice([i[0] for i in Interrogation.STATUS]),
                emitting_institution=institution,
                )
            a.save()
            print "Interrogazione %s - %s creata" % (a.idnum, a.title)

        print "ok"


    def create_tags(self):
        """
        Create a bunch of tags, loaded from an external file. 
        """
        print "Creating tags..."
        # Clear existing tag records
        Tag.objects.all().delete()
        try:
            for line in open(os.path.join(self.APP_ROOT, 'tags.txt')):
                Tag.objects.create(name=line.strip().lower())
        except IOError as e:
            print "Error while opening file: %s" % e
            sys.exit(1)
            
    def create_categories(self):
        """
        Create a bunch of categories, loaded from an external file. 
        """
        print "Creating categories..."
        # Clear existing category records
        Category.objects.all().delete()
        try:
            for line in open(os.path.join(self.APP_ROOT, 'categories.txt')):
                Category.objects.create(name=line.strip().lower())
        except IOError as e:
            print "Error while opening file: %s" % e
            sys.exit(1)
            
    def classify_acts(self):
        """
        Classify each act in the database, by adding to it a random number of categories and,
        for each category, a random number of tags.  
        """
        print  "Classifying acts..."  
        for act in Act.objects.all():
            print  "        act #%s... " % act.pk
            # draw a random subset of categories            
            population = list(Category.objects.all())
            sample_size = random.randint(conf.MIN_CATEGORIES_PER_ACT, conf.MAX_CATEGORIES_PER_ACT)
            categories = random.sample(population, sample_size)
            for category in categories:
                # add category to the act
                act.category_set.add(category)
                # draw a random subset of tags
                population = list(Tag.objects.all())
                sample_size = random.randint(conf.MIN_TAGS_PER_CATEGORY, conf.MAX_TAGS_PER_CATEGORY)
                tags = random.sample(population, sample_size)
                # add tags to the act
                act.tag_set.add(*tags)
                # associate tags with the category
                category.tag_set.add(*tags)
                
    def bookmark_acts(self):
        """
        Add the "key" status to a random subset of the acts stored within the DB.   
        """
        print  "Bookmarkings acts..."
        for act in Act.objects.all():
            if random.random() < conf.KEY_ACTS_RATIO:
                act.is_key = True
                act.save()
                print  "        act #%s is key..." % act.pk

    def generate_dataset(self):
        """
        Generate a random dataset for test purposes. 
        """
        ## acts generation
        self.create_acts()
        ## taxonomy generation
        self.create_tags()
        self.create_categories()
        self.classify_acts()
        self.bookmark_acts()

    #
    # utilities
    #
    @classmethod
    def unify(cls, seq, idfun=None):
        """
        remove double elements from the seq list
        idfun is a callback to the identity function
        """
        # order preserving
        if idfun is None:
            def idfun(x): return x
        seen = {}
        result = []
        for item in seq:
            marker = idfun(item)
            # in old Python versions:
            # if seen.has_key(marker)
            # but in new ones:
            if marker in seen: continue
            seen[marker] = 1
            result.append(item)
        return result

    @classmethod
    def create_person(cls):
        """
        create a random person in the db and return the person just created
        if the person already exists, return it
        """

        try:
            op_path = os.path.join(settings.PROJECT_ROOT, "testdatabuilder", "openpolis_samples")
            f = open(os.path.join(op_path, "op_politician_first_names_sex.csv"), "r")
            l = open(os.path.join(op_path, "op_politician_last_names.csv"), "r")
            loc = open(os.path.join(op_path, "op_politician_birth_locations.csv"), "r")
            dat = open(os.path.join(op_path, "op_politician_birth_dates.csv"), "r")

            first_names = cls.unify(f.readlines())
            last_names = cls.unify(l.readlines())
            birth_dates = cls.unify(dat.readlines())
            birth_locations = cls.unify(loc.readlines())

            first_name = random.choice(first_names)
            first_names.remove(first_name)
            first_name = first_name.strip()
            (names, sex) = first_name.split(',')
            if sex == 'M':
                sex = Person.MALE_SEX
            else:
                sex = Person.FEMALE_SEX
            names = names.split()
            first_name = random.choice(names)

            last_name = random.choice(last_names)
            last_names.remove(last_name)
            last_name = last_name.strip()

            birth_date = random.choice(birth_dates)
            birth_dates.remove(birth_date)
            birth_date = birth_date.strip()
            birth_date = datetime.datetime.strptime(birth_date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")

            birth_location = random.choice(birth_locations)
            birth_locations.remove(birth_location)
            birth_location = birth_location.strip()

            persons = Person.objects.filter(first_name=first_name, last_name=last_name, birth_date=birth_date, birth_location=birth_location)
            if not persons:
                p = Person(first_name=first_name, last_name=last_name, birth_date=birth_date, birth_location=birth_location, sex=sex)
                p.save()
            else:
                p = persons[0]

            return p


        except IOError as e:
            print "Error while opening file: %s" % e
            return 0

    @classmethod
    def get_institution_charges(cls, institution='consiglio', majority=True, n=2):
        """
        returns a number of random institution charges, taken from a group
        or the group in majorities or opposition, as specified in the arguments

        prerequisites: at least n charges of that group must already exist
        if the number of charges is not sufficient, the maximum number is returned
        the function may return no charges (empty array) if the criteria are not matched
        """


        charges = []
        if majority:
            maj_gcharges = list(GroupCharge.objects.filter(group__groupismajority__is_majority=True,
                                                           group__groupismajority__end_date__isnull=True))

            rnd_gcharges = random.sample(maj_gcharges, n)
            for gcharge in rnd_gcharges:
                charges.append(gcharge.charge)

        return charges


    @classmethod
    def generate_random_act_attach(cls, act, n=1):
        """
        generates n random pdf attachments for an act

        title and body, are built using a lorem ipsum generator

        the attachments are built with text and a pdf file upload is simulated
        """
        # random title and body generation
        g = lipsum.MarkupGenerator()

        for i in range(1, n+1):
            title = g.generate_sentences_plain(1)
            body = g.generate_paragraphs_plain(random.randint(3, 50), start_with_lorem=True)

            # attach object created and saved
            attach = Attach(act=act, title=title, text=body)
            attach.save()

            #
            # pdf document generation and upload in proper directory
            #

            # document setup
            if act is not None:
                header = "Atto %s - ###Title###" % (act.idnum,)
            else:
                header = "###Title###"
            footer = "###Section### - Pagina: ###Page###"
            text = "%s\n%s\n%s\n" % ("=" * int(len(title)*1.5), title, "=" * int(len(title)*1.5))
            text += body

            # pdf saved into tmp file
            file_name = "%s_%s.pdf" % (act.idnum, attach.id)
            tmp_file = os.path.join("/tmp", file_name)
            rst2pdf = RstToPdf(breaklevel=0, header=header, footer=footer)
            rst2pdf.createPdf(text=text,
                              output=tmp_file)

            # file is saved as attribute of the attach object and moved in the right path
            # see https://docs.djangoproject.com/en/dev/ref/models/fields/#django.db.models.FieldFile.save
            f = open(tmp_file, 'r')
            attach.pdf_file.save(file_name, File(f))
            attach.save()
            os.remove(tmp_file)

            print "%s: %s uploaded" % (i, file_name)


    @classmethod
    def weighted_choice(cls, weights):
        """
        choice of one element out of a weighted range
        """
        choice = random.random() * sum(weights)
        for i, w in enumerate(weights):
            choice -= w
            if choice < 0:
                return i



if __name__ == '__main__':
    RandomItemsFactory().generate_dataset()
        
